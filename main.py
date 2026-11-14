"""Punto de entrada de Mi Quiosco POS.

La preparación de base de datos, seguridad e integraciones vive en
``app_runtime`` por compatibilidad. La interfaz se construye desde los
módulos ``ui_*`` mediante un ``UIContext`` explícito.
"""

import os
import threading

from ui_app import build_login


def main():
    # Se importa aquí para que ``import main`` sea seguro para herramientas
    # de mantenimiento y pruebas que no desean iniciar la base ni Tkinter.
    from app_runtime import (
        app,
        crear_contexto_ui,
        hilo_bot_telegram,
        iniciar_ui,
        SCREEN_H,
        SCREEN_W,
        DIRECTORIO_BASE,
    )

    app.title("Mi Quiosco POS - Iniciar Sesión")
    icono = os.path.join(DIRECTORIO_BASE, "icono.ico")
    if os.path.exists(icono):
        try:
            app.iconbitmap(icono)
        except Exception:
            pass

    app.deiconify()
    app.state("zoomed")
    app.lift()
    app.attributes("-topmost", True)
    app.after_idle(app.attributes, "-topmost", False)
    app.focus_force()

    threading.Thread(target=hilo_bot_telegram, daemon=True).start()
    contexto_ui = crear_contexto_ui()
    build_login(contexto_ui, iniciar=iniciar_ui)
    app.mainloop()


if __name__ == "__main__":
    main()
