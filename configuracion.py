import os

IMPRIMIR_EN_PAPEL = True
CARPETA_BACKUPS = "Backups_Quiosco"
HABILITAR_TELEGRAM = os.environ.get("HABILITAR_TELEGRAM", "True").lower() == "true"
MI_CUIT = int(os.environ.get("AFIP_CUIT", "20123456789"))
PUNTO_DE_VENTA = int(os.environ.get("AFIP_PUNTO_VENTA", "1"))
MODO_PRODUCCION = os.environ.get("MODO_PRODUCCION", "False").lower() == "true"
tema_oscuro = False
usuario_actual = ""
rol_actual = ""
carrito = []
