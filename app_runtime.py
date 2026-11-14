"""Inicialización y runtime del sistema Mi Quiosco POS."""

import csv
import logging
import os
import shutil
import sqlite3
import stat
import threading
from datetime import datetime
from tkinter import messagebox, simpledialog

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import ttkbootstrap as tb

from base_datos import crear_conexion, formato_limpio, inicializar_tablas, parsear_numero
from configuracion import (
    CARPETA_BACKUPS,
    HABILITAR_TELEGRAM,
    IMPRIMIR_EN_PAPEL,
    MI_CUIT,
    MODO_PRODUCCION,
    PUNTO_DE_VENTA,
    carrito,
    rol_actual,
    tema_oscuro,
    usuario_actual,
)
from seguridad import (
    Afip,
    CRYPTO_OK,
    DIRECTORIO_BASE,
    LIBRERIA_AFIP_OK,
    LIBRERIA_TELEGRAM_OK,
    actualizar_hash_integridad,
    backup_diario,
    cifrar,
    descifrar,
    hashear_clave,
    ruta_appdata,
    ruta_db,
    telebot,
    verificar_licencia_hardware,
)
from servicios import (
    emitir_factura_arca as emitir_factura_arca_externa,
    imprimir_en_ticketera as imprimir_en_ticketera_externa,
)
from telegram_bot import iniciar_bot
from ui_app import build_login, iniciar_app as iniciar_app_ui
from ui_context import UIContext

logging.basicConfig(
    filename="error.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

db_lock = threading.Lock()
app = tb.Window(themename="cosmo")
app.withdraw()
app.update_idletasks()

SCREEN_W = app.winfo_screenwidth()
SCREEN_H = app.winfo_screenheight()

# Escala adaptable según resolución de referencia (1366x768)
SCALE = max(0.7, min(2.0, min(SCREEN_W / 1366.0, SCREEN_H / 768.0)))
BASE_FONT = max(9, int(11 * SCALE))
HEADING_FONT = max(11, int(13 * SCALE))
ROWHEIGHT = max(20, int(35 * SCALE))

app.style.configure("TButton", font=("Segoe UI", BASE_FONT))
app.style.configure("Treeview", font=("Segoe UI", BASE_FONT), rowheight=ROWHEIGHT)
app.style.configure("Treeview.Heading", font=("Segoe UI", HEADING_FONT, "bold"))

# Conexión principal e inicialización de tablas
conexion = crear_conexion(ruta_db)
cursor = conexion.cursor()
inicializar_tablas(conexion)


def registrar_auditoria(accion, detalle="", nivel="INFO"):
    fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    usr = usuario_actual if usuario_actual else "SISTEMA"
    try:
        with db_lock:
            cursor.execute(
                "INSERT INTO auditoria (fecha, usuario, accion, detalle, nivel) VALUES (?, ?, ?, ?, ?)",
                (fecha_ahora, usr, accion, detalle, nivel),
            )
            conexion.commit()
    except Exception as exc:
        logging.error("Fallo al guardar auditoría: %s", exc)


# Importación inicial de productos si la base está vacía
cursor.execute("SELECT COUNT(*) FROM productos")
if cursor.fetchone()[0] == 0:
    ruta_csv = os.path.join(DIRECTORIO_BASE, "lista_precios.csv")
    if os.path.exists(ruta_csv):
        try:
            with open(ruta_csv, "r", encoding="utf-8", errors="replace") as archivo_csv:
                lector = csv.reader(archivo_csv, delimiter=",")
                next(lector, None)
                productos_a_cargar = []
                for fila in lector:
                    if len(fila) >= 5:
                        codigo = fila[0].strip()
                        nombre = fila[1].strip().upper()
                        categoria = fila[2].strip()
                        precio = parsear_numero(fila[3])
                        stock = parsear_numero(fila[4])
                        productos_a_cargar.append((codigo, nombre, categoria, precio, stock))
                if productos_a_cargar:
                    cursor.executemany(
                        "INSERT INTO productos (codigo, nombre, categoria, precio, stock) VALUES (?, ?, ?, ?, ?)",
                        productos_a_cargar,
                    )
                    conexion.commit()
        except Exception as exc:
            logging.error("Error al importar CSV inicial: %s", exc)

# Configuración por defecto si no existe
cursor.execute("SELECT COUNT(*) FROM configuracion")
if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO configuracion (id, nombre_negocio, direccion_negocio, mensaje_ticket, cuit_cifrado, punto_venta, telegram_token_cifrado, telegram_chat_id_cifrado) "
        "VALUES (1, 'MI NEGOCIO', 'Direccion 123', '¡Gracias por su compra!', '20123456789', 1, '', '')"
    )
    conexion.commit()

# Usuario admin inicial desde variable de entorno si aún no existe
def asegurar_admin_inicial(conn, *, clave_env=None):
    """Crea el usuario 'admin' desde KIOSCO_ADMIN_PASSWORD si no hay administradores."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM usuarios WHERE rol='admin'")
    if cur.fetchone()[0] > 0:
        return True
    clave = clave_env if clave_env is not None else os.environ.get("KIOSCO_ADMIN_PASSWORD", "")
    if not clave:
        return False
    cur.execute(
        "INSERT INTO usuarios (usuario, clave, rol) VALUES ('admin', ?, 'admin')",
        (hashear_clave(clave),),
    )
    conn.commit()
    return True


asegurar_admin_inicial(conexion)

# Configuración de clave AFIP si existe en directorio base
ruta_key_appdata = os.path.join(ruta_appdata, "key.key")
ruta_key_local = os.path.join(DIRECTORIO_BASE, "key.key")
if os.path.exists(ruta_key_local) and not os.path.exists(ruta_key_appdata):
    try:
        shutil.copy(ruta_key_local, ruta_key_appdata)
        os.chmod(ruta_key_appdata, stat.S_IREAD | stat.S_IWRITE)
    except Exception:
        pass
if os.path.exists(ruta_key_appdata):
    os.environ["AFIP_KEY_PATH"] = ruta_key_appdata


def obtener_config():
    """Recupera la configuración asegurando compatibilidad de texto plano y descifrado."""
    try:
        cursor.execute(
            "SELECT nombre_negocio, direccion_negocio, mensaje_ticket, cuit_cifrado, punto_venta, "
            "telegram_token_cifrado, telegram_chat_id_cifrado FROM configuracion WHERE id=1"
        )
        fila = cursor.fetchone()
        if not fila:
            return ("MI NEGOCIO", "", "", str(MI_CUIT), PUNTO_DE_VENTA, "", "")
        nombre, direccion, mensaje, cuit_val, pv, token_val, chat_val = fila
        cuit = descifrar(cuit_val) or str(MI_CUIT)
        token = descifrar(token_val) or os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = descifrar(chat_val) or os.environ.get("TELEGRAM_CHAT_ID", "")
        return (nombre or "MI NEGOCIO", direccion or "", mensaje or "", cuit, pv or 1, token, chat_id)
    except Exception as exc:
        logging.error("Error al obtener config: %s", exc)
        return ("MI NEGOCIO", "", "", str(MI_CUIT), PUNTO_DE_VENTA, "", "")


# Backup preventivo diario
backup_diario()


def hilo_bot_telegram():
    """Inicia el bot de Telegram en segundo plano si está configurado."""
    if not LIBRERIA_TELEGRAM_OK or not HABILITAR_TELEGRAM:
        return
    config = obtener_config()
    token = config[5] if config else ""
    if not token or ":" not in token or len(token) < 20:
        return

    def obtener_chat_id():
        conn = sqlite3.connect(ruta_db, timeout=5)
        try:
            fila = conn.execute(
                "SELECT telegram_chat_id_cifrado FROM configuracion WHERE id=1"
            ).fetchone()
            chat_db = descifrar(fila[0]) if fila and fila[0] else ""
            return chat_db or os.environ.get("TELEGRAM_CHAT_ID", "")
        finally:
            conn.close()

    iniciar_bot(
        telebot=telebot,
        ruta_db=ruta_db,
        db_lock=db_lock,
        token=token,
        obtener_chat_id=obtener_chat_id,
        registrar_auditoria=registrar_auditoria,
        obtener_usuario=lambda: usuario_actual,
        app=app,
        mostrar_mensaje=messagebox.showinfo,
        formato_limpio=formato_limpio,
    )


def emitir_factura_arca(total, tipo_factura, doc_nro):
    return emitir_factura_arca_externa(
        total,
        tipo_factura,
        doc_nro,
        libreria_disponible=LIBRERIA_AFIP_OK,
        clase_afip=Afip,
        ruta_appdata=ruta_appdata,
        ruta_key=os.environ.get("AFIP_KEY_PATH"),
        modo_produccion=MODO_PRODUCCION,
        obtener_config=obtener_config,
        cuit_predeterminado=MI_CUIT,
        punto_venta_predeterminado=PUNTO_DE_VENTA,
    )


def imprimir_en_ticketera(texto_ticket):
    imprimir_en_ticketera_externa(
        texto_ticket,
        imprimir_en_papel=IMPRIMIR_EN_PAPEL,
        ruta_ticket=os.path.join(DIRECTORIO_BASE, "ultimo_ticket.txt"),
    )


def crear_contexto_ui():
    """Construye el contexto compartido para la interfaz."""
    contexto = UIContext(
        app=app,
        conexion=conexion,
        cursor=cursor,
        db_lock=db_lock,
        screen_w=SCREEN_W,
        screen_h=SCREEN_H,
        base_font=BASE_FONT,
        heading_font=HEADING_FONT,
        rowheight=ROWHEIGHT,
        usuario=usuario_actual,
        rol=rol_actual,
        carrito=carrito,
        tema_oscuro=tema_oscuro,
    )

    def verificar_admin_ui():
        if contexto.rol == "admin":
            return True
        clave_admin = simpledialog.askstring(
            "Autorización", "Clave de Administrador:", show="*", parent=app
        )
        if not clave_admin:
            return False
        contexto.cursor.execute(
            "SELECT 1 FROM usuarios WHERE rol='admin' AND clave=?",
            (hashear_clave(clave_admin),),
        )
        if contexto.cursor.fetchone():
            return True
        messagebox.showerror("Denegado", "Clave incorrecta.")
        return False

    contexto.callbacks.update({
        "parsear_numero": parsear_numero,
        "formato_limpio": formato_limpio,
        "obtener_config": obtener_config,
        "actualizar_hash_integridad": lambda *args, **kwargs: None,
        "registrar_auditoria": registrar_auditoria,
        "verificar_admin": verificar_admin_ui,
        "emitir_factura_arca": emitir_factura_arca,
        "imprimir_en_ticketera": imprimir_en_ticketera,
        "cifrar": cifrar,
        "descifrar": descifrar,
        "hashear_clave": hashear_clave,
    })
    contexto.ruta_db = ruta_db
    contexto.carpeta_backups = CARPETA_BACKUPS
    return contexto


def iniciar_ui(contexto):
    global usuario_actual, rol_actual
    usuario_actual, rol_actual = contexto.usuario, contexto.rol
    iniciar_app_ui(contexto)


if __name__ == "__main__":
    app.title("Mi Quiosco POS - Iniciar Sesión")
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

