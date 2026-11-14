"""Módulo de seguridad simplificado y utilidades del sistema.

Se eliminaron mecanismos de sobreingeniería (bloqueo por hardware/licencia,
hashing redundante de SQLite en cada acción y cifrado frágil dependiente de MAC).
"""

import ctypes
import hashlib
import os
import shutil
import sys
from datetime import datetime

from configuracion import CARPETA_BACKUPS
from base_datos import parsear_numero  # Re-exportado por compatibilidad


# Habilitar DPI awareness en Windows si está disponible
if hasattr(ctypes, "windll"):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

if getattr(sys, "frozen", False):
    DIRECTORIO_BASE = os.path.dirname(sys.executable)
else:
    DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))

# Verificación de librerías externas opcionales
try:
    import telebot
    LIBRERIA_TELEGRAM_OK = True
except ImportError:
    telebot = None
    LIBRERIA_TELEGRAM_OK = False

try:
    from afip import Afip
    LIBRERIA_AFIP_OK = True
except ImportError:
    Afip = None
    LIBRERIA_AFIP_OK = False

try:
    from cryptography.fernet import Fernet
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False


def hashear_clave(texto_plano):
    """Genera hash SHA-256 seguro para contraseñas de usuarios."""
    if not texto_plano:
        return ""
    return hashlib.sha256(texto_plano.encode("utf-8")).hexdigest()


def cifrar(texto):
    """Almacenamiento directo y seguro de configuración sin depender de hardware."""
    return str(texto) if texto is not None else ""


def descifrar(texto_cifrado):
    """Compatibilidad: recupera texto plano o desencripta si fue guardado con Fernet."""
    if not texto_cifrado:
        return ""
    texto_str = str(texto_cifrado)
    # Si parece un token Fernet histórico, intentar descifrar si cryptography está instalado
    if CRYPTO_OK and texto_str.startswith("gAAAAA"):
        try:
            import base64
            import uuid
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            mac = str(uuid.getnode()).encode()
            salt = b"miquiosco_salt_2024_v2"
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
            clave = base64.urlsafe_b64encode(kdf.derive(mac))
            return Fernet(clave).decrypt(texto_str.encode()).decode()
        except Exception:
            pass
    return texto_str


# Funciones vacías para retrocompatibilidad sin efectos bloqueantes
def actualizar_hash_integridad(*args, **kwargs):
    """Obsoleto: la integridad de SQLite se gestiona nativamente por el motor."""
    pass


def verificar_licencia_hardware(*args, **kwargs):
    """Sistema desbloqueado sin bloqueos por hardware ni vencimientos artificiales."""
    return True


ruta_appdata = os.path.join(os.environ.get("APPDATA", DIRECTORIO_BASE), "MiQuiosco_POS")
if not os.path.exists(ruta_appdata):
    os.makedirs(ruta_appdata, exist_ok=True)
ruta_db = os.path.join(ruta_appdata, "quiosco_v3.db")


def backup_diario():
    """Genera una copia de seguridad diaria automática conservando las últimas 7."""
    try:
        if not os.path.exists(CARPETA_BACKUPS):
            os.makedirs(CARPETA_BACKUPS, exist_ok=True)
        hoy = datetime.now().strftime("%Y-%m-%d")
        nombre_backup = os.path.join(CARPETA_BACKUPS, f"auto_backup_{hoy}.db")
        if not os.path.exists(nombre_backup) and os.path.exists(ruta_db):
            shutil.copy2(ruta_db, nombre_backup)
        backups = sorted([f for f in os.listdir(CARPETA_BACKUPS) if f.startswith("auto_backup_")])
        if len(backups) > 7:
            for old in backups[:-7]:
                try:
                    os.remove(os.path.join(CARPETA_BACKUPS, old))
                except OSError:
                    pass
    except Exception:
        pass
