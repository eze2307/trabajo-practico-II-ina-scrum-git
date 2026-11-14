"""Pruebas unitarias básicas para Mi Quiosco POS."""

import atexit
import csv
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

_TMP_APPDATA = tempfile.mkdtemp(prefix="kiosco_test_appdata_")
atexit.register(lambda: shutil.rmtree(_TMP_APPDATA, ignore_errors=True))
os.environ["APPDATA"] = _TMP_APPDATA

from base_datos import crear_conexion, formato_limpio, inicializar_tablas, parsear_numero
from seguridad import hashear_clave
from ui_ventas import _crear_ticket


class TestMiQuioscoPOS(unittest.TestCase):
    """Valida utilidades de base de datos, seguridad, tickets e inventario."""

    def test_inicializar_tablas_crea_esquema_completo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ruta_db = os.path.join(tmpdir, "pos_test.db")
            conn = crear_conexion(ruta_db)
            try:
                inicializar_tablas(conn)
                tablas = {
                    fila[0]
                    for fila in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
            finally:
                conn.close()

        self.assertTrue(
            {"productos", "ventas", "usuarios", "configuracion", "auditoria"}.issubset(tablas)
        )

    def test_parsear_numero_y_formato_limpio(self):
        casos_parseo = [
            ("1.250,50", 1250.5),
            ("350,25", 350.25),
            ("42", 42.0),
            ("", 0.0),
            (None, 0.0),
            ("no_numerico", 0.0),
        ]
        for entrada, esperado in casos_parseo:
            self.assertEqual(parsear_numero(entrada), esperado)

        self.assertEqual(formato_limpio(3.0), "3")
        self.assertEqual(formato_limpio(1.25), "1.25")

    def test_hashear_clave(self):
        self.assertEqual(hashear_clave(""), "")
        hash_a = hashear_clave("clave_demo_1")
        hash_b = hashear_clave("clave_demo_1")
        self.assertEqual(len(hash_a), 64)
        self.assertEqual(hash_a, hash_b)
        self.assertNotEqual(hash_a, hashear_clave("otra_clave"))

    def test_crear_ticket_efectivo_y_con_cae(self):
        ctx = SimpleNamespace(
            carrito=[{"nombre": "COCA-COLA ZERO 1.5L", "cantidad": 2.0, "total": 4400.0}],
            formato_limpio=formato_limpio,
        )
        ticket_efectivo = _crear_ticket(
            ctx,
            "MI NEGOCIO",
            "Direccion 123",
            "¡Gracias por su compra!",
            "2026-11-14 15:00:00",
            "T-261114150000",
            "Ticket No Fiscal",
            "Efectivo",
            5000.0,
            0.0,
            600.0,
            "",
            "",
        )
        self.assertIn("TOTAL:         $4400.00", ticket_efectivo)
        self.assertIn("VUELTO:        $600.00", ticket_efectivo)

        ticket_cae = _crear_ticket(
            ctx,
            "MI NEGOCIO",
            "Direccion 123",
            "¡Gracias por su compra!",
            "2026-11-14 15:05:00",
            "T-261114150500",
            "Factura C",
            "Billetera Virtual",
            0.0,
            4400.0,
            0.0,
            "74123456789012",
            "20261124",
        )
        self.assertIn("CAE: 74123456789012", ticket_cae)
        self.assertIn("Vto CAE: 2026-11-24", ticket_cae)

    def test_lista_precios_csv_valido(self):
        ruta_csv = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lista_precios.csv")
        with open(ruta_csv, "r", encoding="utf-8") as archivo:
            lector = csv.reader(archivo)
            cabecera = next(lector)
            filas = [fila for fila in lector if len(fila) >= 5]

        self.assertEqual(cabecera, ["Codigo", "Nombre", "Categoria", "Precio", "Stock"])
        self.assertGreater(len(filas), 0)
        for fila in filas:
            self.assertGreaterEqual(parsear_numero(fila[3]), 0.0)


if __name__ == "__main__":
    unittest.main()
