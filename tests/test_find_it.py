"""Pruebas automatizadas para el juego Find It (Partes 11 y 12)."""

from __future__ import annotations
import io
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
from PIL import Image
from streamlit.testing.v1 import AppTest

from homelens.analisis import verificar_find_it
from homelens.errores import (
    CODIGO_IMAGEN_INVALIDA,
    CODIGO_RESPUESTA_INVALIDA,
    CODIGO_SESION_REQUERIDA,
)
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import (
    ContextoUsuario,
    DesafioFindIt,
    EstadoAnalisis,
    EstadoFindIt,
    Exploracion,
    ImagenPreparada,
    IntentoPractica,
    ObjetoEducativo,
    RecuadroNormalizado,
    ResultadoIntento,
    TipoIntento,
)
from homelens.practicas import (
    construir_intento_find_it,
    obtener_desafios_find_it_disponibles,
)


def _crear_imagen_bytes(ancho: int = 400, alto: int = 300) -> bytes:
    img = Image.new("RGB", (ancho, alto), color=(150, 170, 190))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _crear_imagen_preparada(ancho: int = 400, alto: int = 300) -> ImagenPreparada:
    return ImagenPreparada(
        contenido=_crear_imagen_bytes(ancho, alto),
        mime_type="image/jpeg",
        ancho=ancho,
        alto=alto,
    )


def _crear_cliente_gemini_simulado(payload_dict: dict) -> MagicMock:
    respuesta_mock = SimpleNamespace(
        text=json.dumps(payload_dict),
        usage_metadata=SimpleNamespace(
            prompt_token_count=300,
            candidates_token_count=45,
            thoughts_token_count=10,
            total_token_count=355,
            cached_content_token_count=0,
        ),
    )
    cliente = MagicMock()
    cliente.models.generate_content.return_value = respuesta_mock
    return cliente


class TestVerificacionFindItParte11(unittest.TestCase):
    """Pruebas de verificación multimodal con Gemini simulado (Parte 11)."""

    def setUp(self) -> None:
        self.usuario = ContextoUsuario(
            user_id=uuid4(),
            sesion_id="sesion-find-it-test",
            nombre="Estudiante Test",
            es_demo=True,
        )
        self.imagen = _crear_imagen_preparada()
        self.desafio = DesafioFindIt(
            desafio_id=uuid4(),
            user_id=self.usuario.user_id,
            objeto_origen_id=uuid4(),
            nombre_en="Coffee Mug",
            nombre_es="Taza de café",
            creado_en=datetime.now(timezone.utc),
        )

    def test_verificar_find_it_retorna_encontrado_con_recuadro(self) -> None:
        cliente = _crear_cliente_gemini_simulado(
            {
                "estado": "ENCONTRADO",
                "mensaje": "¡Genial! Encontraste una taza de café.",
                "recuadro_encontrado": {"ymin": 100, "xmin": 200, "ymax": 600, "xmax": 700},
            }
        )
        adaptador = AdaptadorGemini(cliente=cliente, max_reintentos=0)

        res = verificar_find_it(
            usuario=self.usuario,
            imagen=self.imagen,
            desafio=self.desafio,
            operacion_id=uuid4(),
            adaptador=adaptador,
        )

        self.assertTrue(res.ok)
        self.assertIsNotNone(res.valor)
        self.assertEqual(res.valor.estado, EstadoFindIt.ENCONTRADO)
        self.assertIn("taza de café", res.valor.mensaje)
        self.assertIsNotNone(res.valor.recuadro_encontrado)
        self.assertEqual(res.valor.recuadro_encontrado.ymin, 100)
        self.assertEqual(res.valor.recuadro_encontrado.xmax, 700)

        intento = construir_intento_find_it(self.usuario, self.desafio, res.valor)
        self.assertIsInstance(intento, IntentoPractica)
        self.assertEqual(intento.tipo, TipoIntento.FIND_IT)
        self.assertEqual(intento.resultado, ResultadoIntento.CORRECTO)
        self.assertEqual(intento.desafio_id, self.desafio.desafio_id)
        self.assertEqual(intento.objeto_ids, [self.desafio.objeto_origen_id])

    def test_verificar_find_it_retorna_no_encontrado(self) -> None:
        cliente = _crear_cliente_gemini_simulado(
            {
                "estado": "NO_ENCONTRADO",
                "mensaje": "No se ve ninguna taza de café en la foto. ¡Sigue buscando!",
                "recuadro_encontrado": None,
            }
        )
        adaptador = AdaptadorGemini(cliente=cliente, max_reintentos=0)

        res = verificar_find_it(
            usuario=self.usuario,
            imagen=self.imagen,
            desafio=self.desafio,
            operacion_id=uuid4(),
            adaptador=adaptador,
        )

        self.assertTrue(res.ok)
        self.assertEqual(res.valor.estado, EstadoFindIt.NO_ENCONTRADO)
        self.assertIsNone(res.valor.recuadro_encontrado)

        intento = construir_intento_find_it(self.usuario, self.desafio, res.valor)
        self.assertEqual(intento.resultado, ResultadoIntento.INCORRECTO)

    def test_verificar_find_it_retorna_indeterminable_como_estado_propio(self) -> None:
        cliente = _crear_cliente_gemini_simulado(
            {
                "estado": "INDETERMINABLE",
                "mensaje": "La foto está demasiado borrosa para confirmar el objeto.",
                "recuadro_encontrado": None,
            }
        )
        adaptador = AdaptadorGemini(cliente=cliente, max_reintentos=0)

        res = verificar_find_it(
            usuario=self.usuario,
            imagen=self.imagen,
            desafio=self.desafio,
            operacion_id=uuid4(),
            adaptador=adaptador,
        )

        self.assertTrue(res.ok)
        self.assertEqual(res.valor.estado, EstadoFindIt.INDETERMINABLE)
        self.assertIsNone(res.valor.recuadro_encontrado)

        intento = construir_intento_find_it(self.usuario, self.desafio, res.valor)
        self.assertEqual(intento.resultado, ResultadoIntento.INDETERMINABLE)

    def test_verificar_find_it_valida_entradas_y_estado_invalido(self) -> None:
        res_sin_usuario = verificar_find_it(None, self.imagen, self.desafio, uuid4())  # type: ignore[arg-type]
        self.assertFalse(res_sin_usuario.ok)
        self.assertEqual(res_sin_usuario.error.codigo, CODIGO_SESION_REQUERIDA)

        res_sin_img = verificar_find_it(self.usuario, None, self.desafio, uuid4())  # type: ignore[arg-type]
        self.assertFalse(res_sin_img.ok)
        self.assertEqual(res_sin_img.error.codigo, CODIGO_IMAGEN_INVALIDA)

        cliente_invalido = _crear_cliente_gemini_simulado(
            {"estado": "DESCONOCIDO", "mensaje": "x", "recuadro_encontrado": None}
        )
        adaptador = AdaptadorGemini(cliente=cliente_invalido, max_reintentos=0)
        res_estado = verificar_find_it(
            usuario=self.usuario,
            imagen=self.imagen,
            desafio=self.desafio,
            operacion_id=uuid4(),
            adaptador=adaptador,
        )
        self.assertFalse(res_estado.ok)
        self.assertEqual(res_estado.error.codigo, CODIGO_RESPUESTA_INVALIDA)

    def test_obtener_desafios_prioriza_exploracion_activa_y_agrega_base(self) -> None:
        exp_id = uuid4()
        obj = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=exp_id,
            nombre_en="Toaster",
            nombre_es="Tostadora",
            recuadro=RecuadroNormalizado(100, 100, 400, 400),
            frase_en="The toaster is on the counter.",
            frase_es="La tostadora está sobre la mesada.",
        )
        exp = Exploracion(
            exploracion_id=exp_id,
            user_id=self.usuario.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[obj],
        )

        desafios = obtener_desafios_find_it_disponibles(self.usuario, exp)
        self.assertGreaterEqual(len(desafios), 7)
        self.assertEqual(desafios[0].nombre_en, "Toaster")
        self.assertEqual(desafios[0].objeto_origen_id, obj.objeto_id)


class TestPantallaFindItParte12(unittest.TestCase):
    """Pruebas de flujo interactivo en la pantalla Find It mediante AppTest (Parte 12)."""

    def _construir_apptest(self, estado_simulado: str) -> AppTest:
        codigo = f"""
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
from PIL import Image
import streamlit as st

from homelens.analisis import verificar_find_it
from homelens.config import Configuracion
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import ContextoUsuario
from homelens.ui.estado import inicializar_estado_sesion
from homelens.ui.find_it import renderizar_pantalla_find_it

inicializar_estado_sesion()
if st.session_state.usuario is None:
    st.session_state.usuario = ContextoUsuario(
        user_id=uuid4(),
        sesion_id="sesion-ui-find-it",
        nombre="Estudiante UI",
        es_demo=True,
    )

cfg = Configuracion(
    app_env="development",
    debug=True,
    log_level="INFO",
    app_port=8501,
    gemini_api_key="test-key",
    gemini_model="gemini-3.6-flash",
    gemini_timeout_seconds=30.0,
    gemini_max_retries=0,
    supabase_url=None,
    supabase_anon_key=None,
    supabase_service_role_key=None,
    google_tts_language_code="en-US",
    google_tts_voice_name="en-US-Standard-C",
    max_image_size_bytes=5_000_000,
    audio_cache_ttl_seconds=3600,
    rate_limit_exploraciones_por_minuto=10,
)

def _verificar_simulado(usuario, imagen, desafio, op_id):
    payload = {{
        "ENCONTRADO": {{
            "estado": "ENCONTRADO",
            "mensaje": f"¡Bien! Encontraste {{desafio.nombre_en}}.",
            "recuadro_encontrado": {{"ymin": 100, "xmin": 100, "ymax": 500, "xmax": 500}},
        }},
        "NO_ENCONTRADO": {{
            "estado": "NO_ENCONTRADO",
            "mensaje": f"No se observó {{desafio.nombre_en}} en la imagen.",
            "recuadro_encontrado": None,
        }},
        "INDETERMINABLE": {{
            "estado": "INDETERMINABLE",
            "mensaje": "No se pudo determinar: intenta con mejor iluminación.",
            "recuadro_encontrado": None,
        }},
    }}["{estado_simulado}"]

    cliente = MagicMock()
    cliente.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(payload),
        usage_metadata=None,
    )
    adaptador = AdaptadorGemini(cliente=cliente, max_reintentos=0)
    return verificar_find_it(usuario, imagen, desafio, op_id, adaptador=adaptador)

renderizar_pantalla_find_it(cfg, verificar_fn=_verificar_simulado)
"""
        return AppTest.from_string(codigo)

    def _inyectar_foto(self, at: AppTest, color: tuple[int, int, int] = (120, 140, 160)) -> None:
        img = Image.new("RGB", (320, 240), color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw = buf.getvalue()
        from homelens.imagenes import preparar_imagen

        prep = preparar_imagen(raw, max_bytes=5_000_000, max_dimension_px=1280).valor
        at.session_state["find_it_imagen_bytes"] = raw
        at.session_state["find_it_imagen_preparada"] = prep

    def test_flujo_completo_tres_resultados_y_volver_a_intentar(self) -> None:
        for estado_esperado in ("ENCONTRADO", "NO_ENCONTRADO", "INDETERMINABLE"):
            with self.subTest(estado=estado_esperado):
                at = self._construir_apptest(estado_esperado)
                at.run()
                self.assertEqual(len(at.exception), 0)

                # Subir foto y ejecutar verificación
                self._inyectar_foto(at)
                at.run()
                btn_verif = next(b for b in at.button if b.key == "btn_verificar_find_it")
                btn_verif.click().run()
                self.assertEqual(len(at.exception), 0)

                verif = at.session_state["find_it_verificacion"]
                self.assertIsNotNone(verif)
                self.assertEqual(verif.estado.value, estado_esperado)

                intento = at.session_state["find_it_ultimo_intento"]
                self.assertIsNotNone(intento)
                self.assertEqual(intento.tipo, TipoIntento.FIND_IT)

                # Volver a intentar limpia foto y resultado, pero conserva el desafío
                btn_retry = next(b for b in at.button if b.key == "btn_reintentar_find_it")
                btn_retry.click().run()
                self.assertEqual(len(at.exception), 0)
                self.assertIsNone(at.session_state["find_it_imagen_bytes"])
                self.assertIsNone(at.session_state["find_it_imagen_preparada"])
                self.assertIsNone(at.session_state["find_it_verificacion"])
                self.assertIsNone(at.session_state["find_it_ultimo_intento"])

    def test_cambiar_desafio_limpia_resultado_anterior(self) -> None:
        at = self._construir_apptest("ENCONTRADO")
        at.run()
        self._inyectar_foto(at)
        at.run()

        btn_verif = next(b for b in at.button if b.key == "btn_verificar_find_it")
        btn_verif.click().run()
        self.assertIsNotNone(at.session_state["find_it_verificacion"])

        # Cambiar al segundo desafío en el selectbox
        selector = at.selectbox[0]
        selector.select_index(1).run()
        self.assertEqual(len(at.exception), 0)
        self.assertIsNone(at.session_state["find_it_verificacion"])
        self.assertIsNone(at.session_state["find_it_ultimo_intento"])

    def test_cambiar_foto_limpia_resultado_anterior(self) -> None:
        from homelens.ui.find_it import renderizar_pantalla_find_it  # noqa: F401
        at = self._construir_apptest("ENCONTRADO")
        at.run()
        self._inyectar_foto(at, color=(100, 100, 100))
        at.run()

        btn_verif = next(b for b in at.button if b.key == "btn_verificar_find_it")
        btn_verif.click().run()
        self.assertIsNotNone(at.session_state["find_it_verificacion"])

        # Simular cambio de archivo subido limpiando resultado mediante el flujo de la UI
        from unittest.mock import patch
        nueva_img_bytes = _crear_imagen_bytes(320, 240)
        with patch("streamlit.file_uploader", return_value=SimpleNamespace(getvalue=lambda: nueva_img_bytes)):
            at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertIsNone(at.session_state["find_it_verificacion"])
        self.assertIsNone(at.session_state["find_it_ultimo_intento"])
        self.assertEqual(at.session_state["find_it_imagen_bytes"], nueva_img_bytes)

    def test_pantalla_dibuja_recuadro_al_verificar_encontrado_con_coordenadas(self) -> None:
        """Verifica que al pulsar Verificar Desafío con ENCONTRADO y coordenadas, se dibuje el recuadro en la imagen mostrada."""
        from unittest.mock import patch

        at = self._construir_apptest("ENCONTRADO")
        at.run()
        self._inyectar_foto(at, color=(120, 140, 160))
        at.run()

        with patch("homelens.ui.find_it.dibujar_recuadros", wraps=__import__("homelens.exploracion", fromlist=["dibujar_recuadros"]).dibujar_recuadros) as mock_dibujar:
            btn_verif = next(b for b in at.button if b.key == "btn_verificar_find_it")
            btn_verif.click().run()

            self.assertEqual(len(at.exception), 0)
            mock_dibujar.assert_called_once()
            verif = at.session_state["find_it_verificacion"]
            self.assertEqual(verif.estado, EstadoFindIt.ENCONTRADO)
            self.assertIsNotNone(verif.recuadro_encontrado)


if __name__ == "__main__":
    unittest.main()
