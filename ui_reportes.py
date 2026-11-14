"""Reportes, administración y acciones secundarias de la aplicación."""

import os
import shutil
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import ttkbootstrap as tb

from ui_context import dimensionar_ventana


def alternar_tema(ctx):
    ctx.tema_oscuro = not ctx.tema_oscuro
    ctx.app.style.theme_use("darkly" if ctx.tema_oscuro else "cosmo")
    ctx.app.style.configure("Treeview", font=("Segoe UI", ctx.base_font), rowheight=ctx.rowheight)
    ctx.app.style.configure("Treeview.Heading", font=("Segoe UI", ctx.heading_font, "bold"))
    boton = ctx.widget("btn_tema")
    boton.config(
        text="☀️ Modo Claro" if ctx.tema_oscuro else "🌙 Modo Oscuro",
        bootstyle="light-outline" if ctx.tema_oscuro else "dark-outline",
    )
    ctx.mostrar_productos()


def ver_estadisticas(ctx):
    try:
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    except ImportError:
        return messagebox.showerror("Aviso", "Instalá matplotlib para ver gráficos: pip install matplotlib")
    ctx.cursor.execute(
        "SELECT p.nombre, SUM(v.cantidad) FROM ventas v JOIN productos p ON v.producto_id = p.id "
        "GROUP BY p.nombre ORDER BY SUM(v.cantidad) DESC LIMIT 5"
    )
    datos = ctx.cursor.fetchall()
    if not datos:
        return messagebox.showinfo("Sin Datos", "Aún no hay ventas registradas.")
    ventana = tb.Toplevel(ctx.app)
    ventana.title("Dashboard de Ventas")
    dimensionar_ventana(ventana, ctx.screen_w, ctx.screen_h, .65, .65)
    fondo, texto = ("#222222", "white") if ctx.tema_oscuro else ("white", "black")
    figura, eje = plt.subplots(figsize=(6, 4))
    figura.patch.set_facecolor(fondo)
    eje.set_facecolor(fondo)
    eje.tick_params(colors=texto)
    eje.bar([fila[0] for fila in datos], [fila[1] for fila in datos],
            color=["#28a745", "#007bff", "#ffc107", "#dc3545", "#6f42c1"])
    eje.set_title("Top 5 Productos Vendidos", color=texto)
    eje.set_ylabel("Cantidades", color=texto)
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    canvas = FigureCanvasTkAgg(figura, master=ventana)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


def cierre_de_caja(ctx):
    hoy = datetime.now().strftime("%Y-%m-%d")
    ctx.cursor.execute("SELECT SUM(total) FROM ventas WHERE fecha LIKE ?", (f"{hoy}%",))
    total = ctx.cursor.fetchone()[0] or 0.0
    if not messagebox.askyesno(
        "Cierre de Caja",
        f"Recaudación total de hoy ({hoy}):\n\n$ {total:.2f}\n\n¿Deseas realizar el cierre y generar una copia de seguridad?",
    ):
        return
    os.makedirs(ctx.carpeta_backups, exist_ok=True)
    ruta = os.path.join(ctx.carpeta_backups, f"respaldo_{datetime.now():%Y-%m-%d_%H-%M-%S}.db")
    try:
        shutil.copy2(ctx.ruta_db, ruta)
        messagebox.showinfo("Copia Generada", f"Copia de seguridad guardada con éxito en:\n{ruta}")
        ctx.registrar_auditoria("Backup Creado", "Se generó una copia de seguridad manual de la base de datos.")
    except Exception as exc:
        messagebox.showerror("Error", f"No se pudo crear el backup:\n{exc}")


def mostrar_historial(ctx):
    if not ctx.verificar_admin():
        return
    ventana = tb.Toplevel(ctx.app)
    ventana.title("Historial de Ventas")
    dimensionar_ventana(ventana, ctx.screen_w, ctx.screen_h, .78, .75)
    ventana.grab_set()
    tb.Label(ventana, text="Historial de Ventas (Últimas 100)",
             font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(pady=10)
    frame = tb.Frame(ventana)
    frame.pack(fill="both", expand=True, padx=20, pady=5)
    columnas = ("ID", "Fecha", "N° Ticket", "Producto", "Cant", "Total", "Pago")
    tabla = tb.Treeview(frame, columns=columnas, show="headings")
    for col in columnas:
        tabla.heading(col, text=col)
        tabla.column(col, width=120 if col != "Producto" else 220,
                     anchor="w" if col == "Producto" else "center")
    scroll = tb.Scrollbar(frame, orient="vertical", command=tabla.yview)
    tabla.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    tabla.pack(side="left", fill="both", expand=True)

    def cargar():
        for fila in tabla.get_children():
            tabla.delete(fila)
        ctx.cursor.execute(
            "SELECT v.id, v.fecha, v.recibo_id, p.nombre, v.cantidad, v.total, "
            "v.metodo_pago, v.producto_id FROM ventas v LEFT JOIN productos p "
            "ON v.producto_id=p.id ORDER BY v.id DESC LIMIT 100"
        )
        for fila in ctx.cursor.fetchall():
            valores = (fila[0], fila[1], fila[2], fila[3] or "Producto Borrado",
                       ctx.formato_limpio(fila[4]), f"${fila[5]:.2f}", fila[6])
            tabla.insert("", "end", values=valores, tags=(str(fila[7]), str(fila[4])))

    def anular():
        seleccion = tabla.selection()
        if not seleccion:
            return messagebox.showwarning("Atención", "Seleccioná una venta de la lista.")
        item = tabla.item(seleccion[0])
        if not messagebox.askyesno(
            "Anular Venta",
            f"¿Anular la venta de {item['values'][3]}?\n\nLa venta se borrará y el stock volverá al inventario.",
        ):
            return
        tags = item["tags"]
        try:
            with ctx.db_lock:
                with ctx.conexion:
                    ctx.cursor.execute("DELETE FROM ventas WHERE id=?", (item["values"][0],))
                    if tags and tags[0] != "None":
                        ctx.cursor.execute(
                            "UPDATE productos SET stock=stock+? WHERE id=?", (float(tags[1]), tags[0])
                        )
            cargar()
            ctx.mostrar_productos()
            messagebox.showinfo("Éxito", "Venta anulada correctamente.")
            ctx.registrar_auditoria(
                "Venta Anulada", f"Se anuló la venta ID: {item['values'][0]} - Producto: {item['values'][3]}",
                nivel="WARNING",
            )
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    cargar()
    tb.Button(ventana, text="❌ Anular Venta Seleccionada", bootstyle="danger",
              command=anular).pack(pady=10)


def ver_auditoria(ctx):
    if not ctx.verificar_admin():
        return
    ventana = tb.Toplevel(ctx.app)
    ventana.title("Auditoría de Acciones")
    dimensionar_ventana(ventana, ctx.screen_w, ctx.screen_h, .80, .70)
    frame = tb.Frame(ventana)
    frame.pack(fill="both", expand=True, padx=20, pady=10)
    columnas = ("ID", "Fecha", "Usuario", "Acción", "Detalle")
    tabla = tb.Treeview(frame, columns=columnas, show="headings")
    for col in columnas:
        tabla.heading(col, text=col)
        tabla.column(col, width=250 if col == "Detalle" else 110)
    tabla.pack(side="left", fill="both", expand=True)
    scroll = tb.Scrollbar(frame, orient="vertical", command=tabla.yview)
    scroll.pack(side="right", fill="y")
    tabla.configure(yscrollcommand=scroll.set)
    conn = sqlite3.connect(ctx.ruta_db, timeout=5)
    try:
        for fila in conn.execute(
            "SELECT id, fecha, usuario, accion, detalle FROM auditoria ORDER BY id DESC LIMIT 200"
        ):
            tabla.insert("", "end", values=fila)
    finally:
        conn.close()


def configurar_sistema(ctx):
    if not ctx.verificar_admin():
        return
    ventana = tb.Toplevel(ctx.app)
    ventana.title("Configuración General")
    dimensionar_ventana(ventana, ctx.screen_w, ctx.screen_h, .65, .75)
    tb.Label(ventana, text="Ajustes del Kiosco y Facturación",
             font=("Segoe UI", 16, "bold")).pack(pady=10)
    conf = ctx.obtener_config()
    campos = {}
    for fila, (texto, valor) in enumerate((
        ("Nombre Local: ", conf[0]), ("Dirección: ", conf[1]), ("Mensaje Ticket: ", conf[2]),
        ("Tu CUIT: ", conf[3] or ""), ("Punto de Venta: ", str(conf[4])),
        ("Token Telegram: ", conf[5] or ""), ("Chat ID Telegram: ", conf[6] or ""),
    )):
        frame = tb.Frame(ventana)
        frame.pack(fill="x", expand=True, pady=3, padx=20)
        tb.Label(frame, text=texto, width=18, anchor="w").pack(side="left", padx=5)
        entrada = tb.Entry(frame)
        entrada.insert(0, valor)
        entrada.pack(side="left", fill="x", expand=True)
        campos[fila] = entrada

    def guardar():
        try:
            punto_venta = int(campos[4].get())
        except ValueError:
            return messagebox.showerror("Error", "El Punto de Venta debe ser un número entero.")
        valores = (
            campos[0].get().upper(), campos[1].get(), campos[2].get(),
            campos[3].get().strip(), punto_venta,
            campos[5].get().strip(), campos[6].get().strip(),
        )
        ctx.cursor.execute(
            "UPDATE configuracion SET nombre_negocio=?, direccion_negocio=?, mensaje_ticket=?, "
            "cuit_cifrado=?, punto_venta=?, telegram_token_cifrado=?, telegram_chat_id_cifrado=? WHERE id=1",
            valores,
        )
        ctx.conexion.commit()
        ctx.app.title(f"POS: {valores[0]} - Cajero: {ctx.usuario.capitalize()}")
        ctx.registrar_auditoria("Configuración Cambiada", f"Nuevo nombre: {valores[0]}")
        messagebox.showinfo("Éxito", "¡Datos actualizados correctamente!")
        ventana.destroy()

    tb.Button(ventana, text="💾 Guardar Cambios", bootstyle="success",
              command=guardar).pack(fill="x", padx=20, pady=20)


def gestionar_usuarios(ctx):
    if not ctx.verificar_admin():
        return
    ventana = tb.Toplevel(ctx.app)
    ventana.title("Usuarios y Empleados")
    dimensionar_ventana(ventana, ctx.screen_w, ctx.screen_h, .62, .68)
    tb.Label(ventana, text="Gestión de Empleados",
             font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(pady=10)
    columnas = ("ID", "Usuario", "Clave", "Rol")
    tabla = tb.Treeview(ventana, columns=columnas, show="headings", height=5)
    for col in columnas:
        tabla.heading(col, text=col, anchor="center")
        tabla.column(col, width=100, anchor="center")
    tabla.pack(fill="x", padx=15, pady=5)

    def cargar():
        for fila in tabla.get_children():
            tabla.delete(fila)
        ctx.cursor.execute("SELECT id, usuario, '******', rol FROM usuarios")
        for usuario in ctx.cursor.fetchall():
            tabla.insert("", "end", values=usuario)

    form = tb.Frame(ventana)
    form.pack(pady=15)
    entradas = []
    for fila, texto, kwargs in (
        (0, "Nombre: ", {}), (1, "Clave: ", {"show": "*"}),
    ):
        tb.Label(form, text=texto).grid(row=fila, column=0, padx=5, pady=5)
        entrada = tb.Entry(form, **kwargs)
        entrada.grid(row=fila, column=1, padx=5, pady=5)
        entradas.append(entrada)
    tb.Label(form, text="Rol: ").grid(row=2, column=0, padx=5, pady=5)
    rol = tb.Combobox(form, values=["cajero", "admin"], state="readonly")
    rol.current(0)
    rol.grid(row=2, column=1, padx=5, pady=5)

    def agregar():
        usuario, clave = entradas[0].get().strip(), entradas[1].get().strip()
        if not usuario or not clave:
            return messagebox.showwarning("Atención", "Completar todos los campos.")
        ctx.cursor.execute("SELECT id FROM usuarios WHERE usuario=?", (usuario,))
        if ctx.cursor.fetchone():
            return messagebox.showerror("Error", "El usuario ya existe.")
        ctx.cursor.execute(
            "INSERT INTO usuarios (usuario, clave, rol) VALUES (?, ?, ?)",
            (usuario, ctx.hashear_clave(clave), rol.get()),
        )
        ctx.conexion.commit()
        cargar()
        for entrada in entradas:
            entrada.delete(0, tk.END)
        ctx.registrar_auditoria("Usuario Creado", f"Usuario: {usuario} - Rol: {rol.get()}", nivel="WARNING")

    cargar()
    tb.Button(ventana, text="Agregar Nuevo Empleado", bootstyle="success",
              command=agregar).pack()


def build_report_buttons(ctx, parent):
    frame = tb.Frame(parent)
    frame.pack_propagate(True)
    acciones = (
        ("📈 Dashboard", ver_estadisticas, "info"),
        ("📜 Historial", mostrar_historial, "primary"),
        ("👁️ Auditoría", ver_auditoria, "secondary"),
        ("⚙️ Ajustes", configurar_sistema, "secondary"),
        ("👥 Usuarios", gestionar_usuarios, "secondary"),
        ("📦 Cierre Z", cierre_de_caja, "warning"),
    )
    botones = []
    for texto, funcion, estilo in acciones:
        botones.append(tb.Button(
            frame, text=texto, bootstyle=estilo,
            command=lambda f=funcion: f(ctx),
        ))
    boton = tb.Button(
        frame, text="☀️ Modo Claro" if ctx.tema_oscuro else "🌙 Modo Oscuro",
        bootstyle="dark-outline", command=lambda: alternar_tema(ctx),
    )
    botones.append(boton)

    def acomodar_acciones(event=None):
        frame.update_idletasks()
        ancho = event.width if event else frame.winfo_width()
        ancho_boton = max(widget.winfo_reqwidth() for widget in botones)
        columnas = max(1, min(len(botones), ancho // ancho_boton))
        for indice, widget in enumerate(botones):
            widget.grid(row=indice // columnas, column=indice % columnas,
                        padx=3, pady=3, sticky="ew")
        for columna in range(columnas):
            frame.columnconfigure(columna, weight=1)
        for fila in range((len(botones) + columnas - 1) // columnas):
            frame.rowconfigure(fila, weight=1)

    frame.bind("<Configure>", acomodar_acciones)
    frame.after_idle(acomodar_acciones)
    ctx.widgets["btn_tema"] = boton
    return frame
