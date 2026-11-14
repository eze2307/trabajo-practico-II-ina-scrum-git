"""Orquestación de la ventana principal y del formulario de acceso."""

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as tb

from ui_productos import create_catalog_form
from ui_reportes import build_report_buttons
from ui_ventas import build_ventas, cobrar_carrito


def iniciar_app(ctx):
    ctx.app.style.configure("Treeview", font=("Segoe UI", ctx.base_font), rowheight=ctx.rowheight)
    ctx.app.style.configure("Treeview.Heading", font=("Segoe UI", ctx.heading_font, "bold"))
    ctx.app.title(f"POS: {ctx.obtener_config()[0]} - Cajero: {ctx.usuario.capitalize()}")
    principal = tb.Frame(ctx.app)
    principal.pack(fill="both", expand=True)
    principal.rowconfigure(0, weight=0)
    principal.rowconfigure(1, weight=1)
    principal.rowconfigure(2, weight=0)
    principal.columnconfigure(0, weight=1)
    formulario = tb.Frame(principal)
    formulario.grid(row=0, column=0, sticky="ew")
    cuerpo = tb.Frame(principal)
    cuerpo.grid(row=1, column=0, sticky="nsew", padx=20)
    catalogo = tb.Labelframe(cuerpo, text=" Catálogo de Productos  ", padding=10)
    catalogo.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=5)
    create_catalog_form(ctx, formulario, catalogo)
    build_ventas(ctx, cuerpo)
    barra = build_report_buttons(ctx, principal)
    barra.grid(row=2, column=0, sticky="ew", padx=20, pady=8)

    def adaptar_distribucion(event=None):
        """Apila los paneles cuando el ancho no permite usarlos lado a lado."""
        ancho = event.width if event else cuerpo.winfo_width()
        modo = "apilado" if ancho < ctx.screen_w * .75 else "columnas"
        if ctx.widgets.get("layout_mode") == modo:
            return
        ctx.widgets["layout_mode"] = modo
        ventas = ctx.widget("frame_ventas")
        catalogo.pack_forget()
        ventas.pack_forget()
        if modo == "apilado":
            catalogo.pack(side="top", fill="both", expand=True, padx=5, pady=(5, 3))
            ventas.pack(side="top", fill="both", expand=True, padx=5, pady=(3, 5))
        else:
            catalogo.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=5)
            ventas.pack(side="right", fill="both", expand=True, padx=0, pady=5)

    ctx.widgets["layout_mode"] = None
    cuerpo.bind("<Configure>", adaptar_distribucion)
    cuerpo.after_idle(adaptar_distribucion)
    ctx.app.bind("<F5>", lambda event: cobrar_carrito(ctx, event))
    ctx.mostrar_productos()
    ctx.widget("entrada_id").focus()


def build_login(ctx, iniciar=None):
    """Crea el acceso y devuelve la función de validación para pruebas/integración."""
    login = tb.Frame(ctx.app)
    login.pack(expand=True)
    tb.Label(login, text="INICIAR SESIÓN",
             font=("Segoe UI", 20, "bold")).pack(pady=20)
    tiene_admin = ctx.cursor.execute(
        "SELECT COUNT(*) FROM usuarios WHERE rol='admin'"
    ).fetchone()[0] > 0
    usuarios = [fila[0] for fila in ctx.cursor.execute(
        "SELECT usuario FROM usuarios ORDER BY usuario"
    ).fetchall()]
    combo = tb.Combobox(login, values=usuarios or ["admin"],
                        state="readonly", font=("Segoe UI", 14))
    combo.pack(pady=10)
    combo.current(0)
    if not tiene_admin:
        tb.Label(
            login,
            text="Primer inicio: la clave ingresada configurará al usuario 'admin'.",
            font=("Segoe UI", 10),
            bootstyle="info",
        ).pack(pady=(0, 8))
    clave = tb.Entry(login, show="*", font=("Segoe UI", 14))
    clave.pack(pady=15)

    def validar(event=None):
        usuario = combo.get()
        clave_texto = clave.get()
        if not ctx.cursor.execute(
            "SELECT COUNT(*) FROM usuarios WHERE rol='admin'"
        ).fetchone()[0]:
            if not clave_texto.strip():
                return messagebox.showwarning(
                    "Configuración inicial",
                    "Ingresá una clave inicial para crear el usuario administrador.",
                )
            with ctx.db_lock:
                ctx.cursor.execute(
                    "INSERT INTO usuarios (usuario, clave, rol) VALUES ('admin', ?, 'admin')",
                    (ctx.hashear_clave(clave_texto),),
                )
                ctx.conexion.commit()
            ctx.usuario, ctx.rol = "admin", "admin"
            login.destroy()
            (iniciar or iniciar_app)(ctx)
            return

        ctx.cursor.execute(
            "SELECT rol FROM usuarios WHERE usuario=? AND clave=?",
            (usuario, ctx.hashear_clave(clave_texto)),
        )
        resultado = ctx.cursor.fetchone()
        if not resultado:
            return messagebox.showerror("Error", "Clave incorrecta")
        ctx.usuario, ctx.rol = usuario, resultado[0]
        login.destroy()
        (iniciar or iniciar_app)(ctx)

    clave.bind("<Return>", validar)
    tb.Button(login, text="Ingresar", bootstyle="success",
              command=validar).pack(pady=20)
    clave.focus()
    return validar
