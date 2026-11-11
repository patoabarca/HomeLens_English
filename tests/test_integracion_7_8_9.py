"""Pruebas de integración de extremo a extremo para las Tareas 7, 8 y 9.

Verifica la coexistencia de:
1. Persistencia y recuperación de exploraciones (M7 - Tarea 7).
2. Conservación íntegra de actividades para cuestionarios tras recuperar (M6 - Tarea 9).
3. Audio bajo demanda con caché en sesión y cliente simulado (M5 - Tarea 8).
4. Limpieza integral de sesión y aislamiento sin llamadas a Gemini.
"""

from __future__ import annotations
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from uuid import UUID, uuid4
import streamlit as st

from homelens.modelos import (
    ContextoUsuario,
    Exploracion,
    ObjetoEducativo,
    Actividad,
    Opcion,
    RecuadroNormalizado,
    EstadoAnalisis,
    ResultadoIntento,
    SolicitudAudio,
)
from homelens.datos.supabase import RepositorioSupabase
from homelens.practicas import validar_y_responder_actividad
from homelens.audio import obtener_audio, _CACHE_AUDIO_SESION
from homelens.ui.audio import _contexto_audio
from homelens.ui.estado import (
    inicializar_estado_sesion,
    limpiar_datos_exploracion,
    cerrar_sesion_usuario,
)


class TestIntegracionTareas789(unittest.TestCase):

    def setUp(self) -> None:
        self.usuario = ContextoUsuario(
            user_id=UUID("22222222-3333-4444-5555-666666666666"),
            sesion_id="sesion_integracion_token_123",
            email="estudiante@homelens.edu",
            nombre="Estudiante Integrado",
            es_demo=True,
        )
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        inicializar_estado_sesion()
        st.session_state.usuario = self.usuario
        _CACHE_AUDIO_SESION.clear()

    def tearDown(self) -> None:
        _CACHE_AUDIO_SESION.clear()

    def _crear_exploracion_completa(self) -> Exploracion:
        exp_id = uuid4()
        obj_id = uuid4()
        act_id = uuid4()

        obj = ObjetoEducativo(
            objeto_id=obj_id,
            exploracion_id=exp_id,
            nombre_en="Book",
            nombre_es="Libro",
            recuadro=RecuadroNormalizado(ymin=100, xmin=100, ymax=400, xmax=400),
            frase_en="This is an interesting book.",
            frase_es="Este es un libro interesante.",
        )

        act = Actividad(
            actividad_id=act_id,
            exploracion_id=exp_id,
            objeto_ids=[obj_id],
            pregunta="What is on the desk?",
            opciones=[
                Opcion(opcion_id="opc_1", texto="A book"),
                Opcion(opcion_id="opc_2", texto="A cup"),
                Opcion(opcion_id="opc_3", texto="A chair"),
            ],
            opcion_correcta_id="opc_1",
            explicacion="The object shown is a book.",
        )

        return Exploracion(
            exploracion_id=exp_id,
            user_id=self.usuario.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[obj],
            actividades=[act],
        )

    def test_guardado_y_recuperacion_conserva_actividades_para_cuestionarios(self) -> None:
        """Tarea 7 + Tarea 9: La exploración guardada y luego recuperada debe permitir ejecutar el cuestionario."""
        almacen_demo: dict[UUID, Exploracion] = {}
        repo = RepositorioSupabase(almacen_demo=almacen_demo)

        exp_original = self._crear_exploracion_completa()

        # 1. Guardar exploración (Tarea 7)
        res_guardar = repo.guardar_exploracion(self.usuario, exp_original)
        self.assertTrue(res_guardar.ok)
        self.assertEqual(res_guardar.valor, exp_original.exploracion_id)

        # 2. Recuperar exploración desde historial (Tarea 7)
        res_recuperar = repo.obtener_exploracion(self.usuario, exp_original.exploracion_id)
        self.assertTrue(res_recuperar.ok)
        exp_recuperada = res_recuperar.valor
        self.assertIsNotNone(exp_recuperada)

        # Verificar integridad de actividades y objetos
        self.assertEqual(len(exp_recuperada.objetos), 1)
        self.assertEqual(len(exp_recuperada.actividades), 1)

        act_recuperada = exp_recuperada.actividades[0]
        self.assertEqual(act_recuperada.actividad_id, exp_original.actividades[0].actividad_id)
        self.assertEqual(len(act_recuperada.opciones), 3)

        # 3. Responder actividad recuperada en cuestionario (Tarea 9)
        res_eval = validar_y_responder_actividad(
            usuario=self.usuario,
            actividad=act_recuperada,
            opcion_id="opc_1",
        )
        self.assertTrue(res_eval.ok)
        self.assertEqual(res_eval.valor.resultado, ResultadoIntento.CORRECTO)
        self.assertFalse(res_eval.valor.registrado)

    def test_audio_simulado_bajo_demanda_y_cache_en_exploracion(self) -> None:
        """Tarea 8: Simular síntesis de audio bajo demanda con caché en sesión sin llamadas externas."""
        exp = self._crear_exploracion_completa()
        obj = exp.objetos[0]

        solicitud = SolicitudAudio(
            texto=obj.nombre_en,
            idioma="en-US",
            voz="en-US-Standard-C",
            velocidad=1.0,
        )

        # Simular adaptador TTS con bytes sintéticos
        mock_adaptador = Mock()
        mock_adaptador.sintetizar.return_value = b"\xff\xfb\x90\x44" + b"\x00" * 200

        with patch("homelens.audio._crear_adaptador", return_value=mock_adaptador):
            # Primera solicitud: genera y guarda en caché
            res1 = obtener_audio(self.usuario, solicitud, operacion_id=uuid4())
            self.assertTrue(res1.ok)
            self.assertFalse(res1.valor.reutilizado)
            self.assertEqual(mock_adaptador.sintetizar.call_count, 1)

            # Segunda solicitud del mismo audio: debe ser servido desde la caché sin nueva síntesis
            res2 = obtener_audio(self.usuario, solicitud, operacion_id=uuid4())
            self.assertTrue(res2.ok)
            self.assertTrue(res2.valor.reutilizado)
            self.assertEqual(mock_adaptador.sintetizar.call_count, 1)

    def test_cierre_de_sesion_limpia_audio_cuestionarios_e_historial(self) -> None:
        """Aislamiento total: cerrar sesión descarta audios, cuestionarios e historial de sesión."""
        exp = self._crear_exploracion_completa()
        st.session_state.exploracion_actual = exp
        st.session_state.exploracion_en_vista_historial = exp
        st.session_state.cuestionario_indice_actual = 1
        st.session_state.cuestionario_respuestas = {exp.actividades[0].actividad_id: Mock()}
        st.session_state.exploraciones_guardadas_ids = {exp.exploracion_id}
        st.session_state._exploraciones_demo = {exp.exploracion_id: exp}

        # Simular presencia de audio en caché mediante el contexto de audio UI
        contexto_audio = _contexto_audio(self.usuario)
        solicitud = SolicitudAudio(texto="Book", idioma="en-US", voz="en-US-Standard-C", velocidad=1.0)
        mock_adaptador = Mock()
        mock_adaptador.sintetizar.return_value = b"mp3_bytes"
        with patch("homelens.audio._crear_adaptador", return_value=mock_adaptador):
            obtener_audio(contexto_audio, solicitud, operacion_id=uuid4())

        self.assertGreater(len(_CACHE_AUDIO_SESION), 0)

        # Cerrar sesión
        cerrar_sesion_usuario()

        # Comprobar limpieza estricta
        self.assertIsNone(st.session_state.usuario)
        self.assertIsNone(st.session_state.exploracion_actual)
        self.assertIsNone(st.session_state.exploracion_en_vista_historial)
        self.assertEqual(st.session_state.cuestionario_indice_actual, 0)
        self.assertEqual(st.session_state.cuestionario_respuestas, {})
        self.assertEqual(len(st.session_state.exploraciones_guardadas_ids), 0)
        self.assertEqual(len(st.session_state._exploraciones_demo), 0)
        self.assertEqual(len(_CACHE_AUDIO_SESION), 0)

    def test_cambio_usuario_a_b_sin_fuga_de_datos_en_historial_y_ui(self) -> None:
        """Cambio A -> B: ni el cierre de sesión ni la vista de historial exponen datos de A a B."""
        from homelens.config import cargar_configuracion
        from homelens.ui.historial import renderizar_pantalla_historial

        usuario_a = ContextoUsuario(
            user_id=UUID("11111111-1111-1111-1111-111111111111"),
            sesion_id="jwt_usuario_a",
            email="usuario.a@gmail.com",
            nombre="Usuario A",
            es_demo=False,
        )
        usuario_b = ContextoUsuario(
            user_id=UUID("22222222-2222-2222-2222-222222222222"),
            sesion_id="jwt_usuario_b",
            email="usuario.b@gmail.com",
            nombre="Usuario B",
            es_demo=False,
        )

        exp_a = Exploracion(
            exploracion_id=uuid4(),
            user_id=usuario_a.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=self._crear_exploracion_completa().objetos,
            actividades=[],
        )

        # 1. Simular que A tenía una exploración recuperada abierta en vista de historial y cierra sesión
        st.session_state.usuario = usuario_a
        st.session_state.exploracion_actual = exp_a
        st.session_state.exploracion_en_vista_historial = exp_a
        st.session_state.exploraciones_guardadas_ids = {exp_a.exploracion_id}
        cerrar_sesion_usuario()

        self.assertIsNone(st.session_state.exploracion_en_vista_historial)
        self.assertIsNone(st.session_state.exploracion_actual)
        self.assertEqual(len(st.session_state.exploraciones_guardadas_ids), 0)

        # 2. Defensa en profundidad: incluso si quedara un resto residual de A en session_state al entrar B,
        # renderizar_pantalla_historial lo descarta y nunca llama a mostrar_exploracion.
        st.session_state.usuario = usuario_b
        st.session_state.exploracion_en_vista_historial = exp_a

        cfg = cargar_configuracion().valor
        mock_repo = Mock()
        mock_repo.listar_exploraciones.return_value = Mock(ok=True, valor=[])

        with (
            patch("homelens.ui.historial.RepositorioSupabase", return_value=mock_repo),
            patch("homelens.ui.historial.mostrar_exploracion") as mock_mostrar,
        ):
            renderizar_pantalla_historial(cfg)
            mock_mostrar.assert_not_called()

        self.assertIsNone(st.session_state.exploracion_en_vista_historial)


if __name__ == "__main__":
    unittest.main()
