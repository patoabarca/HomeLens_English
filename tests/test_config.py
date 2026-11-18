"""Pruebas para carga de configuración y aislamiento de secretos."""

import os
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from homelens.config import (
    cargar_configuracion,
    es_creador_autorizado,
    obtener_nombre_creador,
)
from homelens.modelos import ContextoUsuario


class TestConfiguracion(unittest.TestCase):

    def setUp(self):
        self._env_original = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_original)

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

    def test_creadores_autorizados_se_cargan_solo_si_variables_son_validas(self):
        uid_valido = uuid4()
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
            f.write(
                f"CREADOR_ID_PATRICIA={uid_valido}\n"
                "CREADOR_ID_LUCAS=cadena-invalida-no-uuid\n"
                "CREADOR_ID_VICTORIA=\n"
            )
            temp_path = f.name

        try:
            res = cargar_configuracion(ruta_env=temp_path)
            self.assertTrue(res.ok)
            cfg = res.valor
            # Solo Patricia debe estar presente porque Lucas es inválido y Victoria está vacía
            self.assertIn(uid_valido, cfg.creadores_autorizados)
            self.assertEqual(cfg.creadores_autorizados[uid_valido], "Patricia")
            self.assertEqual(len(cfg.creadores_autorizados), 1)

            # Verificación de autorización con usuario real vs usuario no configurado
            usr_patricia = ContextoUsuario(user_id=uid_valido, sesion_id="s1", nombre="P", es_demo=False)
            usr_otro = ContextoUsuario(user_id=uuid4(), sesion_id="s2", nombre="L", es_demo=False)
            self.assertTrue(es_creador_autorizado(usr_patricia, cfg))
            self.assertFalse(es_creador_autorizado(usr_otro, cfg))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_sin_configuracion_creadores_acceso_denegado_por_defecto(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
            f.write(
                "APP_ENV=testing\n"
                "CREADOR_ID_PATRICIA=\n"
                "CREADOR_ID_LUCAS=\n"
                "CREADOR_ID_VICTORIA=\n"
            )
            temp_path = f.name

        try:
            res = cargar_configuracion(ruta_env=temp_path)
            self.assertTrue(res.ok)
            cfg = res.valor
            self.assertEqual(len(cfg.creadores_autorizados), 0)

            usr = ContextoUsuario(user_id=uuid4(), sesion_id="s1", nombre="C", es_demo=False)
            self.assertFalse(es_creador_autorizado(usr, cfg))
            self.assertEqual(obtener_nombre_creador(usr.user_id, cfg), "Otro Integrante")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
