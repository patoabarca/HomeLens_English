"""Pruebas para carga de configuración y aislamiento de secretos."""

import os
import tempfile
import unittest
from homelens.config import cargar_configuracion


class TestConfiguracion(unittest.TestCase):

    def test_cargar_configuracion_por_defecto(self):
        res = cargar_configuracion()
        self.assertTrue(res.ok)
        self.assertIsNotNone(res.valor)
        self.assertEqual(res.valor.max_image_size_bytes, 10_000_000)
        self.assertEqual(res.valor.google_tts_language_code, "en-US")

    def test_cargar_configuracion_desde_archivo_custom(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
            f.write("APP_ENV=testing\nAPP_PORT=9000\nGEMINI_MODEL=gemini-custom\n")
            temp_path = f.name

        try:
            res = cargar_configuracion(ruta_env=temp_path)
            self.assertTrue(res.ok)
            self.assertIsNotNone(res.valor)
            self.assertEqual(res.valor.app_port, 9000)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
