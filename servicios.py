"""Servicios externos de Mi Quiosco POS.

Este módulo concentra las integraciones que no pertenecen a la interfaz:
facturación electrónica e impresión de tickets.
"""

import logging
import os
import sys
from datetime import datetime


def emitir_factura_arca(
    total,
    tipo_factura,
    doc_nro,
    *,
    libreria_disponible,
    clase_afip,
    ruta_appdata,
    ruta_key,
    modo_produccion,
    obtener_config,
    cuit_predeterminado,
    punto_venta_predeterminado,
):
    """Emite una factura y devuelve ``(CAE, vencimiento, mensaje)``."""
    if not libreria_disponible:
        return None, None, "Falta instalar la librería. Ejecutá: pip install afip.py"

    cert_path = os.path.join(ruta_appdata, "cert.crt")
    key_path = ruta_key or os.path.join(ruta_appdata, "key.key")
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        return None, None, "Faltan los archivos cert.crt y key.key en la carpeta segura."

    conf = obtener_config()
    mi_cuit = int(conf[3]) if conf[3] else cuit_predeterminado
    punto_venta = int(conf[4]) if conf[4] else punto_venta_predeterminado
    try:
        afip = clase_afip({
            "CUIT": mi_cuit,
            "cert": cert_path,
            "key": key_path,
            "production": modo_produccion,
        })
        tipos = {"Factura A": 1, "Factura B": 6, "Factura C": 11}
        cbte_tipo = tipos.get(tipo_factura)
        if cbte_tipo is None:
            return None, None, "Tipo de factura no soportado"

        documento = str(doc_nro).replace("-", "").strip()
        if not documento or documento == "0":
            doc_tipo, documento = 99, 0
        elif len(documento) == 11:
            doc_tipo = 80
        else:
            doc_tipo = 96

        ultimo = afip.ElectronicBilling.getLastVoucher(punto_venta, cbte_tipo)
        numero = ultimo + 1
        datos = {
            "cant_reg": 1, "pto_vta": punto_venta, "cbte_tipo": cbte_tipo,
            "concepto": 1, "doc_tipo": doc_tipo, "doc_nro": int(documento),
            "cbte_desde": numero, "cbte_hasta": numero,
            "cbte_fch": int(datetime.now().strftime("%Y%m%d")),
            "imp_total": total, "imp_tot_conc": 0, "imp_neto": total,
            "imp_op_ex": 0, "imp_iva": 0, "imp_trib": 0,
            "mon_id": "PES", "mon_cotiz": 1,
        }
        resultado = afip.ElectronicBilling.createVoucher(datos)
        return resultado["CAE"], resultado["CAEFchVto"], "OK"
    except Exception as exc:
        logging.error("Error ARCA: %s", exc)
        return None, None, f"Error de conexión con ARCA:\n{exc}"


def imprimir_en_ticketera(texto_ticket, *, imprimir_en_papel, ruta_ticket):
    """Guarda el último ticket y, si está habilitado, lo envía a la impresora."""
    try:
        with open(ruta_ticket, "w", encoding="utf-8") as archivo:
            archivo.write(texto_ticket)
        if sys.platform.startswith("win"):
            os.startfile(ruta_ticket)
    except (OSError, AttributeError):
        logging.exception("No se pudo guardar o abrir el último ticket")

    if not imprimir_en_papel:
        return
    try:
        import win32print

        impresora = win32print.GetDefaultPrinter()
        hprinter = win32print.OpenPrinter(impresora)
        try:
            win32print.StartDocPrinter(hprinter, 1, ("Ticket POS", None, "RAW"))
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, texto_ticket.encode("latin-1", errors="replace"))
            win32print.WritePrinter(hprinter, b"\x1d\x56\x41\x03")
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
        finally:
            win32print.ClosePrinter(hprinter)
    except (ImportError, OSError):
        logging.exception("No se pudo imprimir el ticket")
