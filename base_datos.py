"""Utilidades compartidas para el acceso a datos del POS."""

import sqlite3


def crear_conexion(ruta_db):
    """Crea una conexión SQLite con soporte para operaciones entre hilos."""
    return sqlite3.connect(ruta_db, check_same_thread=False)


def formato_limpio(valor):
    """Presenta cantidades sin ceros decimales innecesarios."""
    try:
        numero = float(valor)
        return str(int(numero)) if numero % 1 == 0 else f"{numero:.3f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(valor)


def parsear_numero(valor):
    """Convierte cadenas con coma o punto a float seguro."""
    if valor is None or valor == "":
        return 0.0
    valor = str(valor).strip()
    if "." in valor and "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    elif "," in valor:
        valor = valor.replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return 0.0


def inicializar_tablas(conexion):
    """Crea las tablas esenciales si no existen."""
    cursor = conexion.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT DEFAULT '',
        nombre TEXT,
        categoria TEXT DEFAULT 'General',
        precio REAL,
        stock REAL
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER,
        cantidad REAL,
        total REAL,
        fecha TEXT,
        usuario TEXT DEFAULT 'admin',
        recibo_id TEXT DEFAULT '0000',
        tipo_factura TEXT DEFAULT 'Ticket No Fiscal',
        metodo_pago TEXT DEFAULT 'Efectivo',
        cobro_efectivo REAL DEFAULT 0,
        cobro_virtual REAL DEFAULT 0,
        cliente TEXT DEFAULT 'Consumidor Final',
        cuit TEXT DEFAULT '',
        cae TEXT DEFAULT '',
        vencimiento_cae TEXT DEFAULT ''
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        clave TEXT,
        rol TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS configuracion (
        id INTEGER PRIMARY KEY,
        nombre_negocio TEXT,
        direccion_negocio TEXT,
        mensaje_ticket TEXT,
        cuit_cifrado TEXT DEFAULT '',
        punto_venta INTEGER DEFAULT 1,
        telegram_token_cifrado TEXT DEFAULT '',
        telegram_chat_id_cifrado TEXT DEFAULT ''
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        usuario TEXT,
        accion TEXT,
        detalle TEXT,
        nivel TEXT DEFAULT 'INFO'
    )""")
    conexion.commit()
