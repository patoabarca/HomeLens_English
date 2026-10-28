"""Pruebas de interfaz y AppTest para el flujo de autenticación M1 en Streamlit."""

from __future__ import annotations
import unittest
from unittest.mock import patch
from uuid import UUID

from streamlit.testing.v1 import AppTest

from homelens.acceso import reiniciar_adaptador_global
from homelens.errores import Resultado
from homelens.modelos import ContextoUsuario


from pathlib import Path

RUTA_APP = str(Path(__file__).resolve().parent.parent / "app.py")


class TestUIAcceso(unittest.TestCase):
    """Pruebas interactivas con AppTest para autenticación en app.py."""

    def setUp(self) -> None:
        reiniciar_adaptador_global()
        self.uuid_prueba = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    def tearDown(self) -> None:
        reiniciar_adaptador_global()

    def test_app_sin_autenticar_muestra_pantalla_acceso_y_bloquea_rutas(self) -> None:
        """Verifica que sin sesión activa, la app muestre la pantalla de acceso y bloquee navegación."""
        at = AppTest.from_file(RUTA_APP, default_timeout=15)
        at.run()

        self.assertEqual(len(at.exception), 0, "Fallo al renderizar app sin autenticar")

        # Comprobar que no hay usuario en sesión
        self.assertIsNone(at.session_state.usuario)

        # La navegación solo ofrece 'Acceso / Ingreso'
        self.assertEqual(len(at.radio), 1)
        self.assertIn("Acceso / Ingreso", at.radio[0].options)
        self.assertNotIn("Exploración Visual", at.radio[0].options)

    def test_app_usuario_autenticado_muestra_navegacion_y_boton_cerrar_sesion(self) -> None:
        """Verifica que con usuario autenticado se desbloqueen las secciones y aparezca Cerrar sesión."""
        usuario_valido = ContextoUsuario(
            user_id=self.uuid_prueba,
            sesion_id="token_sesion_verificado_123",
            email="lucas@homelens.edu",
            nombre="Lucas Raul Centurion",
            es_demo=False,
        )

        with patch("homelens.acceso.obtener_usuario_actual", return_value=Resultado.exito(usuario_valido)):
            at = AppTest.from_file(RUTA_APP, default_timeout=15)
            at.session_state.usuario = usuario_valido
            at.run()

            self.assertEqual(len(at.exception), 0, "Fallo con usuario autenticado")

            # Comprobar que se habilitó la navegación completa a las rutas protegidas
            self.assertEqual(len(at.radio), 1)
            opciones = at.radio[0].options
            self.assertTrue(any("Exploraci" in o for o in opciones), "No se encontró Exploración Visual")
            self.assertTrue(any("Inicio" in o for o in opciones), "No se encontró Inicio")

            # Comprobar que existe el botón de Cerrar sesión en la barra lateral
            btn_cerrar = next((b for b in at.button if "Cerrar sesión" in b.label), None)
            self.assertIsNotNone(btn_cerrar, "No se encontró el botón de Cerrar sesión")

            # Pulsar Cerrar sesión
            btn_cerrar.click().run()
            self.assertEqual(len(at.exception), 0, "Fallo al pulsar Cerrar sesión")

            # La sesión debe haber sido eliminada y la navegación reseteada a Acceso
            self.assertIsNone(at.session_state.usuario)
            self.assertIn("Acceso / Ingreso", at.radio[0].options)


if __name__ == "__main__":
    unittest.main()
