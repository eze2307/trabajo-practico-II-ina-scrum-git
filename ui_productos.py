"""Construcción y acciones del catálogo de productos."""

import csv
import logging
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as tb

from ui_context import dimensionar_ventana


def _admin(ctx):
    return ctx.verificar_admin()


def mostrar_productos(ctx):
    entrada = ctx.widget("entrada_busqueda")
    tabla = ctx.widget("tabla")
    termino = entrada.get()
    for fila in tabla.get_children():
        tabla.delete(fila)
    if termino:
        termino = termino.replace("%", "").replace("_", "")
        ctx.cursor.execute(
            "SELECT id, codigo, nombre, categoria, precio, stock FROM productos "
            "WHERE nombre LIKE ? OR codigo LIKE ?",
            (f"%{termino}%", f"%{termino}%"),
        )
    else:
        ctx.cursor.execute(
            "SELECT id, codigo, nombre, categoria, precio, stock FROM productos"
        )
    for id_p, cod, nom, cat, pre, stk in ctx.cursor.fetchall():
        valores = (id_p, cod, nom, cat, f"${pre:.2f}", ctx.formato_limpio(stk))
        tabla.insert(
            "", "end", values=valores,
            tags=("bajo_stock",) if stk <= 5 else (),
        )
    color = "#5c1b1b" if ctx.tema_oscuro else "#ffcccc"
    tabla.tag_configure("bajo_stock", background=color)


def agregar_producto(ctx):
    if not _admin(ctx):
        return
    try:
        codigo = ctx.widget("entrada_codigo").get().strip()
        nombre = ctx.widget("entrada_nombre").get().strip().upper()
        categoria = ctx.widget("combo_categoria").get()
        precio = ctx.parsear_numero(ctx.widget("entrada_precio").get())
        stock = ctx.parsear_numero(ctx.widget("entrada_stock").get())
        if not nombre:
            return messagebox.showwarning("Advertencia", "El producto debe tener un nombre.")
        with ctx.db_lock:
            ctx.cursor.execute(
                "INSERT INTO productos (codigo, nombre, categoria, precio, stock) "
                "VALUES (?, ?, ?, ?, ?)",
                (codigo, nombre, categoria, precio, stock),
            )
            ctx.conexion.commit()
        mostrar_productos(ctx)
        ctx.registrar_auditoria(
            "Producto Creado", f"Cód: {codigo} - Nombre: {nombre} - Stock Inicial: {stock}"
        )
        for nombre_widget in (
            "entrada_codigo", "entrada_nombre", "entrada_precio", "entrada_stock"
        ):
            ctx.widget(nombre_widget).delete(0, tk.END)
    except Exception as exc:
        logging.error("Error al agregar producto: %s", exc)
        messagebox.showerror("Error", f"Revisa los datos ingresados:\n{exc}")


def eliminar_producto(ctx):
    if not _admin(ctx):
        return
    tabla = ctx.widget("tabla")
    seleccion = tabla.selection()
    if not seleccion:
        return messagebox.showwarning("Atención", "Selecciona un producto para eliminar.")
    item = tabla.item(seleccion[0])
    if messagebox.askyesno("Confirmar", f"¿Eliminar el producto '{item['values'][2]}' permanentemente?"):
        with ctx.db_lock:
            ctx.cursor.execute("DELETE FROM productos WHERE id=?", (item["values"][0],))
            ctx.conexion.commit()
        mostrar_productos(ctx)
        ctx.registrar_auditoria(
            "Producto Eliminado",
            f"Se eliminó ID: {item['values'][0]} - Nombre: {item['values'][2]}",
            nivel="WARNING",
        )


def editar_producto(ctx):
    if not _admin(ctx):
        return
    tabla = ctx.widget("tabla")
    seleccion = tabla.selection()
    if not seleccion:
        return messagebox.showwarning("Atención", "Selecciona un producto.")
    item = tabla.item(seleccion[0])
    ventana = tb.Toplevel(ctx.app)
    ventana.title("Editar Producto")
    dimensionar_ventana(ventana, ctx.screen_w, ctx.screen_h, .42, .35)
    ventana.grab_set()
    tb.Label(ventana, text="Nuevo Precio $: ").pack(pady=10)
    precio = tb.Entry(ventana)
    precio.insert(0, str(item["values"][4]).replace("$", ""))
    precio.pack()
    tb.Label(ventana, text="Nuevo Stock: ").pack(pady=10)
    stock = tb.Entry(ventana)
    stock.insert(0, str(item["values"][5]))
    stock.pack()

    def guardar(event=None):
        try:
            nuevo_precio = ctx.parsear_numero(precio.get())
            nuevo_stock = ctx.parsear_numero(stock.get())
            with ctx.db_lock:
                ctx.cursor.execute(
                    "UPDATE productos SET precio=?, stock=? WHERE id=?",
                    (nuevo_precio, nuevo_stock, item["values"][0]),
                )
                ctx.conexion.commit()
            mostrar_productos(ctx)
            ventana.destroy()
            ctx.registrar_auditoria(
                "Producto Editado",
                f"ID: {item['values'][0]} - Nuevo Precio: ${nuevo_precio} - Nuevo Stock: {nuevo_stock}",
            )
        except Exception as exc:
            logging.error("Error al editar producto: %s", exc)
            messagebox.showerror("Error", "Datos inválidos")

    tb.Button(ventana, text="Guardar Cambios", bootstyle="success",
              command=guardar).pack(pady=20)
    ventana.bind("<Return>", guardar)
    ventana.bind("<Escape>", lambda _event: ventana.destroy())


def importar_lista_productos(ctx):
    if not _admin(ctx):
        return
    archivo = filedialog.askopenfilename(
        title="Seleccionar Lista de Productos",
        filetypes=[("Archivo CSV", "*.csv"), ("Todos los archivos", "*.*")],
    )
    if not archivo:
        return
    try:
        nuevos = actualizados = 0
        with open(archivo, "r", encoding="utf-8", errors="replace") as archivo_csv:
            lector = csv.reader(archivo_csv, delimiter=",")
            next(lector, None)
            with ctx.db_lock:
                for fila in lector:
                    if len(fila) < 5:
                        continue
                    codigo, nombre, categoria = fila[0].strip(), fila[1].strip().upper(), fila[2].strip()
                    precio = ctx.parsear_numero(fila[3])
                    stock = ctx.parsear_numero(fila[4])
                    ctx.cursor.execute("SELECT id FROM productos WHERE codigo=? AND codigo != ''", (codigo,))
                    existente = ctx.cursor.fetchone()
                    if existente:
                        ctx.cursor.execute(
                            "UPDATE productos SET precio=?, stock=?, nombre=?, categoria=? WHERE codigo=?",
                            (precio, stock, nombre, categoria, codigo),
                        )
                        actualizados += 1
                    else:
                        ctx.cursor.execute(
                            "INSERT INTO productos (codigo, nombre, categoria, precio, stock) VALUES (?, ?, ?, ?, ?)",
                            (codigo, nombre, categoria, precio, stock),
                        )
                        nuevos += 1
                ctx.conexion.commit()
        mostrar_productos(ctx)
        ctx.registrar_auditoria(
            "Importación de Lista", f"Nuevos: {nuevos} | Actualizados: {actualizados}"
        )
        messagebox.showinfo(
            "¡Carga Exitosa!",
            f"La lista se procesó correctamente.\n\nNuevos agregados: {nuevos}\nActualizados: {actualizados}",
        )
    except Exception as exc:
        logging.error("Error al importar lista: %s", exc)
        messagebox.showerror("Error de Lectura", f"No se pudo leer el archivo.\n\nDetalle técnico: {exc}")


def seleccionar_item(ctx, _event=None):
    seleccion = ctx.widget("tabla").selection()
    if seleccion:
        item = ctx.widget("tabla").item(seleccion[0])
        entrada = ctx.widget("entrada_id")
        entrada.delete(0, tk.END)
        entrada.insert(0, item["values"][1] or item["values"][0])


def doble_click_item(ctx, event=None):
    seleccionar_item(ctx, event)
    entrada = ctx.widget("entrada_cantidad")
    entrada.delete(0, tk.END)
    entrada.insert(0, "1")
    ctx.agregar_al_carrito()


def create_catalog_form(ctx, parent, frame_catalog):
    """Construye formulario superior y catálogo completo."""
    font_ui = ("Segoe UI", 11)
    form = tb.Frame(parent)
    form.pack(fill="x", pady=10, padx=20)

    def campo(texto, nombre, ancho):
        contenedor = tb.Frame(form)
        etiqueta = tb.Label(contenedor, text=texto, font=font_ui)
        etiqueta.pack(side="left", padx=(0, 2))
        widget = tb.Entry(contenedor, width=ancho, font=font_ui)
        widget.pack(side="left", fill="x", expand=True)
        campos.append(contenedor)
        ctx.widgets[nombre] = widget

    campos = []
    campo("Cód: ", "entrada_codigo", 12)
    campo("Nombre: ", "entrada_nombre", 15)
    categoria = tb.Frame(form)
    tb.Label(categoria, text="Cat: ", font=font_ui).pack(side="left", padx=(0, 2))
    combo = tb.Combobox(
        categoria, values=["Bebidas", "Golosinas", "Lácteos", "Pesable", "General"],
        width=10, font=font_ui,
    )
    combo.set("General")
    combo.pack(side="left", fill="x", expand=True)
    campos.append(categoria)
    ctx.widgets["combo_categoria"] = combo
    campo("Precio $: ", "entrada_precio", 8)
    campo("Stock: ", "entrada_stock", 6)
    agregar = tb.Button(form, text="✚ Agregar", bootstyle="success",
                        command=lambda: agregar_producto(ctx))
    campos.append(agregar)

    def acomodar_formulario(event=None):
        ancho = event.width if event else form.winfo_width()
        columnas = 3 if ancho < 900 else 6
        for indice, widget in enumerate(campos):
            widget.grid(row=indice // columnas, column=indice % columnas,
                        padx=4, pady=3, sticky="ew")
        for columna in range(columnas):
            form.columnconfigure(columna, weight=1)

    form.bind("<Configure>", acomodar_formulario)
    form.after_idle(acomodar_formulario)

    busq = tb.Frame(frame_catalog)
    busq.pack(fill="x", pady=5)
    tb.Label(busq, text="Buscar: ", font=font_ui).pack(side="left", padx=5)
    entrada_busqueda = tb.Entry(busq, font=font_ui)
    entrada_busqueda.pack(side="left", fill="x", expand=True, padx=5)
    ctx.widgets["entrada_busqueda"] = entrada_busqueda
    entrada_busqueda.bind("<KeyRelease>", lambda event: mostrar_productos(ctx))
    acciones = tb.Frame(busq)
    acciones.pack(side="right")
    tb.Button(acciones, text="📥 Importar Lista", bootstyle="info",
              command=lambda: importar_lista_productos(ctx)).pack(side="left", padx=2)
    tb.Button(acciones, text="✏️ Editar", bootstyle="warning",
              command=lambda: editar_producto(ctx)).pack(side="left", padx=2)
    tb.Button(acciones, text="🗑️ Eliminar", bootstyle="danger",
              command=lambda: eliminar_producto(ctx)).pack(side="left", padx=2)

    columnas = ("ID", "Cód", "Nombre", "Cat", "Precio", "Stock")
    tabla = tb.Treeview(frame_catalog, columns=columnas, show="headings", height=8)
    ctx.widgets["tabla"] = tabla
    for col in columnas:
        tabla.heading(col, text=col)
    total_w = max(400, int(ctx.screen_w * .5))
    for col, ratio, minimo in (
        ("ID", .06, 40), ("Cód", .10, 60), ("Nombre", .48, 200),
        ("Cat", .12, 80), ("Precio", .10, 80), ("Stock", .08, 60),
    ):
        tabla.column(col, width=max(minimo, int(total_w * ratio)),
                     anchor="center" if col in ("ID", "Stock") else "w")
    scroll = tb.Scrollbar(frame_catalog, orient="vertical", command=tabla.yview)
    scroll_x = tb.Scrollbar(frame_catalog, orient="horizontal", command=tabla.xview)
    tabla.configure(yscrollcommand=scroll.set)
    tabla.configure(xscrollcommand=scroll_x.set)
    scroll.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    tabla.pack(fill="both", expand=True)
    tabla.bind("<ButtonRelease-1>", lambda event: seleccionar_item(ctx, event))
    tabla.bind("<Double-1>", lambda event: doble_click_item(ctx, event))
    ctx.mostrar_productos = lambda: mostrar_productos(ctx)
    ctx.widgets["frame_catalog"] = frame_catalog
    return form
