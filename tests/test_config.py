"""Pruebas para carga de configuración y aislamiento de secretos."""

import os
import tempfile
import unittest
from unittest import mock
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

    def test_cargar_configuracion_sin_archivo_ni_secretos(self):
        variables = {
            "GEMINI_API_KEY": "sentinel-no-real",
            "SUPABASE_URL": "https://example.invalid",
            "SUPABASE_ANON_KEY": "sentinel-no-real",
            "SUPABASE_SERVICE_ROLE_KEY": "sentinel-no-real",
        }
        with mock.patch.dict(os.environ, variables):
            res = cargar_configuracion(cargar_archivo_env=False, incluir_secretos=False)

        self.assertTrue(res.ok)
        self.assertIsNone(res.valor.gemini_api_key)
        self.assertIsNone(res.valor.supabase_url)
        self.assertIsNone(res.valor.supabase_anon_key)
        self.assertIsNone(res.valor.supabase_service_role_key)


if __name__ == "__main__":
    unittest.main()
