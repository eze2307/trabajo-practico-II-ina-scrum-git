"""Bot de Telegram para consultas operativas del punto de venta."""

import logging
import sqlite3
from datetime import datetime


def iniciar_bot(
    *,
    telebot,
    ruta_db,
    db_lock,
    token,
    obtener_chat_id,
    registrar_auditoria,
    obtener_usuario,
    app,
    mostrar_mensaje,
    formato_limpio,
):
    if not token or ":" not in token or len(token) < 20:
        return

    try:
        bot = telebot.TeleBot(token, threaded=True)

        def autorizado(message):
            chat_id = obtener_chat_id()
            if chat_id and str(message.chat.id) == str(chat_id):
                return True
            registrar_auditoria(
                "INTRUSO_TELEGRAM",
                f"Intento acceso Telegram (ID: {message.chat.id})",
                nivel="WARNING",
            )
            return False

        @bot.message_handler(commands=["start", "menu"])
        def mostrar_menu(message):
            if not autorizado(message):
                return
            teclado = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            teclado.add(
                telebot.types.KeyboardButton("📊 Caja del Día"),
                telebot.types.KeyboardButton("📦 Ver Stock"),
                telebot.types.KeyboardButton("👤 Cajero Actual"),
                telebot.types.KeyboardButton("📅 Caja Mensual"),
                telebot.types.KeyboardButton("🚨 Aviso al Local"),
            )
            bot.reply_to(message, "¡Panel de control conectado! Selecciona una opción 👇", reply_markup=teclado)

        @bot.message_handler(func=lambda msg: msg.text in ("📊 Caja del Día", "/caja"))
        def comando_caja(message):
            if not autorizado(message):
                return
            try:
                with db_lock:
                    conn = sqlite3.connect(ruta_db, timeout=5)
                    cur = conn.cursor()
                    hoy = datetime.now().strftime("%Y-%m-%d")
                    cur.execute("SELECT SUM(total), COUNT(*) FROM ventas WHERE fecha LIKE ?", (f"{hoy}%",))
                    total, cantidad = cur.fetchone()
                    cur.execute("SELECT SUM(cobro_efectivo), SUM(cobro_virtual) FROM ventas WHERE fecha LIKE ?", (f"{hoy}%",))
                    efectivo, virtual = cur.fetchone()
                    conn.close()
                bot.reply_to(
                    message,
                    f"📊 *CAJA DEL DÍA* ({hoy})\n\n💵 Efectivo: ${(efectivo or 0):.2f}\n"
                    f"📱 Digital: ${(virtual or 0):.2f}\n------------------\n"
                    f"💰 *TOTAL HOY:* ${(total or 0):.2f}\n🛒 Tickets Emitidos: {cantidad or 0}",
                    parse_mode="Markdown",
                )
            except Exception as exc:
                logging.error("Error en comando /caja: %s", exc)
                bot.reply_to(message, "⚠️ Error al calcular la caja.")

        @bot.message_handler(func=lambda msg: msg.text in ("📦 Ver Stock", "/stock"))
        def comando_stock(message):
            if not autorizado(message):
                return
            try:
                with db_lock:
                    conn = sqlite3.connect(ruta_db, timeout=5)
                    bajos = conn.execute(
                        "SELECT nombre, stock FROM productos WHERE stock <= 5 ORDER BY stock ASC"
                    ).fetchall()
                    conn.close()
                texto = "⚠️ *ALERTA DE INVENTARIO* (≤ 5) ⚠️\n\n"
                texto += "".join(f"• {nombre}: {formato_limpio(stock)} ud.\n" for nombre, stock in bajos)
                bot.reply_to(message, texto if bajos else "✅ El stock se encuentra en niveles óptimos.", parse_mode="Markdown")
            except Exception as exc:
                logging.error("Error en comando /stock: %s", exc)
                bot.reply_to(message, "⚠️ Error al consultar el stock.")

        @bot.message_handler(func=lambda msg: msg.text in ("👤 Cajero Actual", "/cajero"))
        def comando_cajero(message):
            if not autorizado(message):
                return
            usuario = obtener_usuario()
            texto = f"👤 El empleado activo es: *{usuario.capitalize()}*" if usuario else "💻 Sistema en pantalla de acceso. Nadie inició sesión."
            bot.reply_to(message, texto, parse_mode="Markdown")

        @bot.message_handler(func=lambda msg: msg.text in ("📈 Top 5 Vendidos", "/top"))
        def comando_top(message):
            if not autorizado(message):
                return
            try:
                with db_lock:
                    conn = sqlite3.connect(ruta_db, timeout=5)
                    hoy = datetime.now().strftime("%Y-%m-%d")
                    datos = conn.execute(
                        "SELECT p.nombre, SUM(v.cantidad) "
                        "FROM ventas v JOIN productos p ON v.producto_id = p.id "
                        "WHERE v.fecha LIKE ? GROUP BY p.nombre "
                        "ORDER BY SUM(v.cantidad) DESC LIMIT 5",
                        (f"{hoy}%",),
                    ).fetchall()
                    conn.close()
                texto = f"🏆 *TOP 5 DE HOY* ({hoy})\n\n"
                texto += "".join(
                    f"{pos}. {nombre} ({formato_limpio(cantidad)} vendidos)\n"
                    for pos, (nombre, cantidad) in enumerate(datos, 1)
                )
                bot.reply_to(message, texto if datos else "Aún no hay ventas registradas hoy.", parse_mode="Markdown")
            except Exception as exc:
                logging.error("Error en comando /top: %s", exc)
                bot.reply_to(message, "⚠️ Error al consultar el Top 5.")

        @bot.message_handler(func=lambda msg: msg.text in ("📅 Caja Mensual", "/mes"))
        def comando_mes(message):
            if not autorizado(message):
                return
            try:
                with db_lock:
                    conn = sqlite3.connect(ruta_db, timeout=5)
                    mes = datetime.now().strftime("%Y-%m")
                    total, efectivo, virtual = conn.execute(
                        "SELECT SUM(total), SUM(cobro_efectivo), SUM(cobro_virtual) "
                        "FROM ventas WHERE fecha LIKE ?",
                        (f"{mes}%",),
                    ).fetchone()
                    conn.close()
                bot.reply_to(
                    message,
                    f"📅 *RECAUDACIÓN DEL MES* ({mes})\n\n"
                    f"💵 Efectivo: ${(efectivo or 0):.2f}\n📱 Digital: ${(virtual or 0):.2f}\n"
                    f"------------------\n💰 *TOTAL MES:* ${(total or 0):.2f}",
                    parse_mode="Markdown",
                )
            except Exception as exc:
                logging.error("Error en comando /mes: %s", exc)
                bot.reply_to(message, "⚠️ Error al calcular el mes.")

        @bot.message_handler(func=lambda msg: msg.text in ("🚨 Aviso al Local", "/aviso"))
        def comando_aviso(message):
            if not autorizado(message):
                return
            mensaje = bot.reply_to(message, "Escribe el mensaje que quieres mandar a la pantalla de la caja:")
            bot.register_next_step_handler(mensaje, enviar_aviso)

        def enviar_aviso(message):
            app.after(0, lambda: mostrar_mensaje("💬 MENSAJE DEL JEFE", message.text))
            bot.reply_to(message, "✅ Mensaje enviado y mostrado en la PC del local.")

        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as exc:
        logging.warning("El bot de Telegram no pudo iniciarse o se desconectó: %s", exc)
