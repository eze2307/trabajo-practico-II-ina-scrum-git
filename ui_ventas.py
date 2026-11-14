"""Carrito, cobro y emisión de tickets."""

import logging
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import ttkbootstrap as tb


def actualizar_tabla_carrito(ctx):
    tabla = ctx.widget("tabla_carrito")
    for fila in tabla.get_children():
        tabla.delete(fila)
    total = sum(item["total"] for item in ctx.carrito)
    ultimo_item_id = None
    for item in ctx.carrito:
        fila_id = tabla.insert(
            "", "end",
            values=(item["nombre"], ctx.formato_limpio(item["cantidad"]),
                    f"${item['total']:.2f}"),
        )
        ultimo_item_id = fila_id
    ctx.widget("lbl_total_carrito").config(text=f"Total a Cobrar: ${total:.2f}")
    if ultimo_item_id:
        tabla.see(ultimo_item_id)


def agregar_al_carrito(ctx, event=None):
    entrada_id = ctx.widget("entrada_id")
    entrada_cantidad = ctx.widget("entrada_cantidad")
    busqueda = entrada_id.get().strip()
    if not busqueda:
        return
    cantidad_texto = entrada_cantidad.get().strip()
    monto_fijo = cantidad_texto.startswith("$")
    cantidad_texto = cantidad_texto.replace("$", "") if monto_fijo else cantidad_texto
    valor = ctx.parsear_numero(cantidad_texto)
    if valor <= 0:
        valor = 1.0

    ctx.cursor.execute(
        "SELECT id, nombre, precio, stock FROM productos WHERE id=? OR codigo=?",
        (busqueda, busqueda),
    )
    producto = ctx.cursor.fetchone()
    if not producto:
        _beep(1000, 400)
        messagebox.showerror("Error", "Producto no encontrado.")
        entrada_id.delete(0, tk.END)
        entrada_id.focus()
        return

    id_prod, nombre, precio, stock = producto
    cantidad = (valor / precio) if monto_fijo and precio else valor
    existente = next((item for item in ctx.carrito if item["id"] == id_prod), None)
    cantidad_actual = existente["cantidad"] if existente else 0
    if cantidad_actual + cantidad > stock:
        _beep(1000, 400)
        messagebox.showerror("Error", f"Stock insuficiente. Hay: {ctx.formato_limpio(stock)}")
        entrada_id.delete(0, tk.END)
        entrada_id.focus()
        return

    if existente:
        existente["cantidad"] += cantidad
        existente["total"] = existente["cantidad"] * precio
    else:
        ctx.carrito.append({
            "id": id_prod, "nombre": nombre, "precio": precio,
            "cantidad": cantidad, "total": precio * cantidad,
        })
    actualizar_tabla_carrito(ctx)
    _beep(2500, 100)
    entrada_id.delete(0, tk.END)
    entrada_cantidad.delete(0, tk.END)
    entrada_cantidad.insert(0, "1")
    entrada_id.focus()


def _beep(frecuencia, duracion):
    try:
        import winsound
        winsound.Beep(frecuencia, duracion)
    except (ImportError, RuntimeError):
        pass


def eliminar_item_carrito(ctx, event=None):
    tabla = ctx.widget("tabla_carrito")
    seleccion = tabla.selection()
    if not seleccion:
        messagebox.showinfo("Información", "Selecciona un producto del carrito para quitarlo.")
        return
    item = tabla.item(seleccion[0])
    nombre = item["values"][0]
    for indice, carrito_item in enumerate(ctx.carrito):
        if carrito_item["nombre"] == nombre:
            del ctx.carrito[indice]
            break
    actualizar_tabla_carrito(ctx)
    ctx.widget("entrada_id").focus()


def vaciar_carrito(ctx):
    if not ctx.carrito:
        return
    if messagebox.askyesno("Vaciar Carrito", "¿Deseas eliminar todos los productos del carrito?"):
        ctx.carrito.clear()
        actualizar_tabla_carrito(ctx)
        ctx.widget("entrada_id").focus()


def cobrar_carrito(ctx, event=None):
    if not ctx.carrito:
        return messagebox.showwarning("Atención", "El carrito está vacío.")
    total = sum(item["total"] for item in ctx.carrito)
    ventana = tb.Toplevel(ctx.app)
    ventana.title("Finalizar Venta")
    ventana.geometry(
        f"{min(700, int(ctx.screen_w * .35))}x{min(800, int(ctx.screen_h * .65))}"
    )
    ventana.grab_set()
    tb.Label(
        ventana, text=f"Total a pagar: ${total:.2f}",
        font=("Segoe UI", 18, "bold"), bootstyle="success",
    ).pack(pady=10)

    frame_factura = tb.Frame(ventana)
    frame_factura.pack(pady=5)
    tb.Label(frame_factura, text="Tipo de Factura: ",
             font=("Segoe UI", 10, "bold")).grid(row=0, column=0, pady=5)
    combo_factura = tb.Combobox(
        frame_factura,
        values=["Ticket No Fiscal", "Factura A", "Factura B", "Factura C"],
        state="readonly",
    )
    combo_factura.current(0)
    combo_factura.grid(row=0, column=1, pady=5)
    lbl_cuit = tb.Label(frame_factura, text="DNI / CUIT Cliente: ")
    ent_cuit = tb.Entry(frame_factura)
    lbl_cliente = tb.Label(frame_factura, text="Nombre Cliente: ")
    ent_cliente = tb.Entry(frame_factura)

    def actualizar_factura(_event=None):
        if combo_factura.get() != "Ticket No Fiscal":
            lbl_cuit.grid(row=1, column=0, pady=5)
            ent_cuit.grid(row=1, column=1, pady=5)
            lbl_cliente.grid(row=2, column=0, pady=5)
            ent_cliente.grid(row=2, column=1, pady=5)
        else:
            for widget in (lbl_cuit, ent_cuit, lbl_cliente, ent_cliente):
                widget.grid_forget()

    combo_factura.bind("<<ComboboxSelected>>", actualizar_factura)

    frame_pago = tb.Frame(ventana)
    frame_pago.pack(pady=10)
    tb.Label(frame_pago, text="Método de Pago: ",
             font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, pady=5)
    combo_pago = tb.Combobox(
        frame_pago, values=["Efectivo", "Billetera Virtual", "Mixto"],
        state="readonly", font=("Segoe UI", 10),
    )
    combo_pago.current(0)
    combo_pago.grid(row=1, column=0, columnspan=2, pady=5)

    lbl_efectivo = tb.Label(frame_pago, text="Efectivo entregado: $ ")
    lbl_efectivo.grid(row=2, column=0, pady=5, sticky="e")
    ent_efectivo = tb.Entry(frame_pago, font=("Segoe UI", 12))
    ent_efectivo.grid(row=2, column=1, pady=5)
    ent_efectivo.insert(0, f"{total:.2f}")

    lbl_virtual = tb.Label(frame_pago, text="Monto transferido: $ ")
    ent_virtual = tb.Entry(frame_pago, font=("Segoe UI", 12))
    ent_virtual.insert(0, "0.0")

    def actualizar_pago(_event=None):
        metodo = combo_pago.get()
        if metodo == "Efectivo":
            lbl_virtual.grid_forget()
            ent_virtual.grid_forget()
            lbl_efectivo.grid(row=2, column=0, pady=5, sticky="e")
            lbl_efectivo.config(text="Efectivo entregado: $ ")
            ent_efectivo.grid(row=2, column=1, pady=5)
            ent_efectivo.config(state="normal")
            ent_efectivo.delete(0, tk.END)
            ent_efectivo.insert(0, f"{total:.2f}")
            ent_efectivo.focus_set()
        elif metodo == "Billetera Virtual":
            lbl_virtual.grid_forget()
            ent_virtual.grid_forget()
            lbl_efectivo.grid(row=2, column=0, pady=5, sticky="e")
            lbl_efectivo.config(text="Total a transferir: $ ")
            ent_efectivo.grid(row=2, column=1, pady=5)
            ent_efectivo.delete(0, tk.END)
            ent_efectivo.insert(0, f"{total:.2f}")
            ent_efectivo.config(state="disabled")
            ventana.focus_set()
        else:  # Mixto
            lbl_efectivo.grid(row=2, column=0, pady=5, sticky="e")
            lbl_efectivo.config(text="Efectivo entregado: $ ")
            ent_efectivo.grid(row=2, column=1, pady=5)
            ent_efectivo.config(state="normal")
            ent_efectivo.delete(0, tk.END)
            ent_efectivo.insert(0, "0.0")
            lbl_virtual.grid(row=3, column=0, pady=5, sticky="e")
            ent_virtual.grid(row=3, column=1, pady=5)
            ent_virtual.delete(0, tk.END)
            ent_virtual.insert(0, f"{total:.2f}")
            ent_efectivo.focus_set()

    combo_pago.bind("<<ComboboxSelected>>", actualizar_pago)

    def procesar(_event=None):
        metodo = combo_pago.get()
        tipo_factura = combo_factura.get()
        cliente = ent_cliente.get().strip().upper() if tipo_factura != "Ticket No Fiscal" else "CONSUMIDOR FINAL"
        cuit = ent_cuit.get().strip() if tipo_factura != "Ticket No Fiscal" else ""

        if metodo == "Efectivo":
            efectivo = ctx.parsear_numero(ent_efectivo.get())
            if efectivo < total:
                return messagebox.showerror("Error", "El monto ingresado en efectivo es menor al total.")
            cobro_efectivo = efectivo
            cobro_virtual = 0.0
            vuelto = efectivo - total
        elif metodo == "Billetera Virtual":
            cobro_efectivo = 0.0
            cobro_virtual = total
            vuelto = 0.0
        else:  # Mixto
            efectivo = ctx.parsear_numero(ent_efectivo.get())
            virtual = ctx.parsear_numero(ent_virtual.get())
            suma = efectivo + virtual
            if suma < total:
                return messagebox.showerror(
                    "Error", f"La suma ingresada (${suma:.2f}) es menor al total (${total:.2f})."
                )
            cobro_efectivo = efectivo
            cobro_virtual = virtual
            vuelto = max(0.0, suma - total)

        cae = vencimiento = ""
        if tipo_factura != "Ticket No Fiscal":
            cae_result, vencimiento_result, error = ctx.emitir_factura_arca(total, tipo_factura, cuit)
            if not cae_result:
                return messagebox.showerror("Error ARCA", error)
            cae, vencimiento = cae_result, vencimiento_result

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        recibo = f"T-{datetime.now().strftime('%y%m%d%H%M%S')}"
        nombre, direccion, mensaje = ctx.obtener_config()[:3]

        try:
            with ctx.db_lock:
                with ctx.conexion:
                    for item in ctx.carrito:
                        ctx.cursor.execute(
                            "UPDATE productos SET stock = stock - ? WHERE id = ?",
                            (item["cantidad"], item["id"]),
                        )
                        ctx.cursor.execute(
                            "INSERT INTO ventas (producto_id, cantidad, total, fecha, usuario, recibo_id, "
                            "metodo_pago, cobro_efectivo, cobro_virtual, tipo_factura, cliente, cuit, cae, vencimiento_cae) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (item["id"], item["cantidad"], item["total"], fecha, ctx.usuario, recibo,
                             metodo, cobro_efectivo, cobro_virtual, tipo_factura, cliente, cuit, cae, vencimiento),
                        )
        except Exception as exc:
            logging.error("Error al registrar la venta: %s", exc)
            return messagebox.showerror("Error", f"Ocurrió un error al registrar la venta:\n{exc}")

        ctx.mostrar_productos()
        ticket = _crear_ticket(
            ctx, nombre, direccion, mensaje, fecha, recibo, tipo_factura, metodo,
            cobro_efectivo, cobro_virtual, vuelto, cae, vencimiento,
        )
        ctx.imprimir_en_ticketera(ticket)
        if vuelto > 0:
            messagebox.showinfo("Venta Exitosa", f"¡Venta realizada con éxito!\n\nVuelto a entregar: ${vuelto:.2f}")
        else:
            messagebox.showinfo("Venta Exitosa", "¡Venta realizada con éxito!")

        ctx.registrar_auditoria("Venta Realizada", f"Ticket: {recibo} - Total: ${total:.2f}")
        ctx.carrito.clear()
        actualizar_tabla_carrito(ctx)
        ventana.destroy()
        ctx.widget("entrada_id").focus()

    tb.Button(ventana, text="CONFIRMAR VENTA ✅ (Enter)",
              bootstyle="success", command=procesar).pack(pady=20, padx=20)
    ventana.bind("<Return>", procesar)
    ventana.bind("<Escape>", lambda _event: ventana.destroy())
    ventana.after(100, ent_efectivo.focus_set)


def _crear_ticket(ctx, nombre, direccion, mensaje, fecha, recibo, tipo_factura,
                  metodo, cobro_efectivo, cobro_virtual, vuelto, cae, vencimiento):
    total = sum(item["total"] for item in ctx.carrito)
    ticket = f"{nombre.center(32)}\n{direccion.center(32)}\n{'=' * 32}\n"
    ticket += f"Fecha: {fecha}\nTicket: {recibo}\n{tipo_factura.center(32)}\n{'-' * 32}\n"
    for item in ctx.carrito:
        nombre_item = item["nombre"][:15].ljust(15)
        cantidad = f"x{ctx.formato_limpio(item['cantidad'])} ".ljust(7)
        importe = f"${item['total']:.2f} ".rjust(8)
        ticket += f"{nombre_item} {cantidad} {importe}\n"
    ticket += f"{'-' * 32}\n{'TOTAL:'.ljust(15)}${total:.2f}\n"
    if metodo == "Efectivo":
        ticket += f"{'Pago Efvo:'.ljust(15)}${cobro_efectivo:.2f}\n"
    elif metodo == "Billetera Virtual":
        ticket += f"{'Pago Transf:'.ljust(15)}${cobro_virtual:.2f}\n"
    else:
        ticket += f"{'Pago Efvo:'.ljust(15)}${cobro_efectivo:.2f}\n{'Pago Transf:'.ljust(15)}${cobro_virtual:.2f}\n"
    ticket += f"{'VUELTO:'.ljust(15)}${vuelto:.2f}\n{'=' * 32}\n"
    if cae:
        ticket += f"CAE: {cae}\n"
        vencimiento_formateado = (
            f"{vencimiento[:4]}-{vencimiento[4:6]}-{vencimiento[6:]}"
        )
        ticket += f"Vto CAE: {vencimiento_formateado}\n"
    return ticket + f"\n{mensaje.center(32)}\n\n\n\n\n\n"


def build_ventas(ctx, parent):
    frame = tb.Labelframe(parent, text=" Carrito y Venta  ", padding=10)
    frame.pack(side="right", fill="both")
    ctx.widgets["frame_ventas"] = frame

    cobro = tb.Frame(frame)
    cobro.pack(fill="x", pady=5)
    tb.Label(cobro, text="ID/Cód: ").grid(row=0, column=0, padx=5)
    entrada_id = tb.Entry(cobro, width=15)
    entrada_id.grid(row=0, column=1, padx=5)
    tb.Label(cobro, text="Cant: ").grid(row=0, column=2, padx=5)
    entrada_cantidad = tb.Entry(cobro, width=8)
    entrada_cantidad.grid(row=0, column=3, padx=5)
    entrada_cantidad.insert(0, "1")
    ctx.widgets.update(entrada_id=entrada_id, entrada_cantidad=entrada_cantidad)

    agregar = lambda event=None: agregar_al_carrito(ctx, event)
    tb.Button(cobro, text="Sumar 🛒", bootstyle="info",
              command=agregar).grid(row=0, column=4, padx=5)
    entrada_id.bind("<Return>", agregar)

    # Frame contenedor de la tabla del carrito con barra de desplazamiento vertical
    frame_tabla = tb.Frame(frame)
    frame_tabla.pack(fill="both", expand=True, padx=5, pady=5)

    tabla = tb.Treeview(
        frame_tabla,
        columns=("Prod", "Cant", "Total"),
        show="headings",
        height=8,
    )
    tabla.heading("Prod", text="Producto", anchor="w")
    tabla.heading("Cant", text="Cant.", anchor="center")
    tabla.heading("Total", text="Total", anchor="e")
    tabla.column("Prod", width=max(200, int(ctx.screen_w * .32 * .65)), anchor="w")
    tabla.column("Cant", width=60, anchor="center")
    tabla.column("Total", width=80, anchor="e")

    # Scrollbar para que nunca se pierdan los productos al haber muchos ítems
    scroll_y = tb.Scrollbar(frame_tabla, orient="vertical", command=tabla.yview)
    tabla.configure(yscrollcommand=scroll_y.set)
    scroll_y.pack(side="right", fill="y")
    tabla.pack(side="left", fill="both", expand=True)

    # Atajos: Supr o Doble Clic para quitar un ítem del carrito
    tabla.bind("<Delete>", lambda event: eliminar_item_carrito(ctx, event))
    tabla.bind("<Double-1>", lambda event: eliminar_item_carrito(ctx, event))
    ctx.widgets["tabla_carrito"] = tabla

    controles = tb.Frame(frame)
    controles.pack(side="bottom", fill="x", pady=(5, 0))
    lbl = tb.Label(controles, text="Total a Cobrar: $0.00",
                   font=("Segoe UI", 20, "bold"), bootstyle="success")
    lbl.pack(pady=5)
    ctx.widgets["lbl_total_carrito"] = lbl

    # Botones de gestión rápida de ítems
    btn_box = tb.Frame(controles)
    btn_box.pack(fill="x", pady=5)
    tb.Button(
        btn_box, text="❌ Quitar Ítem", bootstyle="warning-outline",
        command=lambda: eliminar_item_carrito(ctx),
    ).pack(side="left", fill="x", expand=True, padx=2)
    tb.Button(
        btn_box, text="🗑️ Vaciar", bootstyle="danger-outline",
        command=lambda: vaciar_carrito(ctx),
    ).pack(side="right", fill="x", expand=True, padx=2)

    tb.Button(
        controles, text="COBRAR 💵 (F5)", bootstyle="success",
        command=lambda: cobrar_carrito(ctx),
    ).pack(pady=5, fill="x")

    ctx.agregar_al_carrito = lambda event=None: agregar_al_carrito(ctx, event)
    ctx.cobrar_carrito = lambda event=None: cobrar_carrito(ctx, event)
