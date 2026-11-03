"""Pruebas unitarias para el módulo M6: Cuestionarios Pedagógicos Interactivos (Tarea 9).

Verifica la evaluación local, validaciones de seguridad, protección de respuestas,
mezcla aleatoria de opciones, estabilidad del orden, opciones inicialmente vacías,
navegación entre preguntas, gestión de estado en sesión y aislamiento.
"""

from __future__ import annotations
import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4
import streamlit as st

from homelens.errores import (
    CODIGO_RESPUESTA_INVALIDA,
    CODIGO_SESION_REQUERIDA,
)
from homelens.modelos import (
    ContextoUsuario,
    Actividad,
    Opcion,
    ActividadPublica,
    ResultadoIntento,
    ResultadoPractica,
    Exploracion,
    ObjetoEducativo,
    RecuadroNormalizado,
    EstadoAnalisis,
)
from homelens.practicas import (
    responder_actividad,
    obtener_actividad_publica,
    mezclar_opciones_actividad,
    validar_y_responder_actividad,
)
from homelens.ui.estado import (
    inicializar_estado_sesion,
    limpiar_datos_cuestionario,
    limpiar_datos_exploracion,
    invalidar_preparacion_anterior,
    cerrar_sesion_usuario,
)


def _crear_actividad_ejemplo(
    actividad_id: UUID | None = None,
    exploracion_id: UUID | None = None,
    opcion_correcta_id: str = "opc_1",
) -> Actividad:
    """Helper para crear una Actividad pedagógica válida con 3 opciones."""
    act_id = actividad_id or uuid4()
    exp_id = exploracion_id or uuid4()
    return Actividad(
        actividad_id=act_id,
        exploracion_id=exp_id,
        objeto_ids=[uuid4()],
        pregunta="What is this object on the table?",
        opciones=[
            Opcion(opcion_id="opc_1", texto="A ceramic mug"),
            Opcion(opcion_id="opc_2", texto="A wooden chair"),
            Opcion(opcion_id="opc_3", texto="An electric lamp"),
        ],
        opcion_correcta_id=opcion_correcta_id,
        explicacion="The object shown is a ceramic mug used for hot drinks.",
    )


class TestCuestionarios(unittest.TestCase):

    def setUp(self) -> None:
        self.usuario_valido = ContextoUsuario(
            user_id=UUID("11111111-2222-3333-4444-555555555555"),
            sesion_id="sesion_test_123",
            email="patricia@homelens.edu",
            nombre="Patricia",
        )
        # Limpiar st.session_state antes de cada prueba
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        inicializar_estado_sesion()
        st.session_state.usuario = self.usuario_valido

    # =========================================================================
    # 1. Pruebas de Dominio Puro: responder_actividad y obtener_actividad_publica
    # =========================================================================

    def test_responder_actividad_acierto(self) -> None:
        """Verifica que responder_actividad detecte correctamente un acierto."""
        intento_id = uuid4()
        res = responder_actividad(
            usuario=self.usuario_valido,
            actividad_id=uuid4(),
            opcion_id="opc_1",
            opcion_correcta_id="opc_1",
            explicacion="Explicación pedagógica",
            intento_id=intento_id,
        )
        self.assertTrue(res.ok)
        self.assertIsNotNone(res.valor)
        self.assertEqual(res.valor.resultado, ResultadoIntento.CORRECTO)
        self.assertEqual(res.valor.intento_id, intento_id)
        self.assertEqual(res.valor.explicacion, "Explicación pedagógica")
        self.assertFalse(res.valor.registrado, "registrado debe ser False para la Tarea 10 de Lucas")

    def test_responder_actividad_error(self) -> None:
        """Verifica que responder_actividad detecte un error pedagógico."""
        intento_id = uuid4()
        res = responder_actividad(
            usuario=self.usuario_valido,
            actividad_id=uuid4(),
            opcion_id="opc_2",
            opcion_correcta_id="opc_1",
            explicacion="Explicación de error",
            intento_id=intento_id,
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.valor.resultado, ResultadoIntento.INCORRECTO)
        self.assertFalse(res.valor.registrado)

    def test_obtener_actividad_publica_no_revela_solucion(self) -> None:
        """Verifica que la proyección pública excluya la respuesta correcta y la explicación."""
        actividad = _crear_actividad_ejemplo()
        pub = obtener_actividad_publica(actividad)

        self.assertIsInstance(pub, ActividadPublica)
        self.assertEqual(pub.actividad_id, actividad.actividad_id)
        self.assertEqual(pub.pregunta, actividad.pregunta)
        self.assertEqual(len(pub.opciones), 3)

        # Invariante de seguridad: ActividadPublica no tiene opcion_correcta_id ni explicacion
        self.assertFalse(hasattr(pub, "opcion_correcta_id"))
        self.assertFalse(hasattr(pub, "explicacion"))

    # =========================================================================
    # 2. Pruebas de Mezcla y Orden de Opciones (Problema 2)
    # =========================================================================

    def test_mezclar_opciones_actividad_invariantes(self) -> None:
        """Verifica que mezclar_opciones_actividad conserve las 3 opciones sin mutar la original."""
        act = _crear_actividad_ejemplo()
        ids_originales = [o.opcion_id for o in act.opciones]

        opciones_mezcladas = mezclar_opciones_actividad(act)

        # 1. La lista original de la actividad no fue modificada
        self.assertEqual([o.opcion_id for o in act.opciones], ids_originales)
        self.assertEqual(len(opciones_mezcladas), 3)

        # 2. Contiene exactamente los mismos elementos
        ids_mezclados = {o.opcion_id for o in opciones_mezcladas}
        self.assertEqual(ids_mezclados, set(ids_originales))

    def test_distribucion_variable_de_posicion_correcta(self) -> None:
        """Verifica estadísticamente que la respuesta correcta pueda aparecer en cualquier posición (A, B o C)."""
        act = _crear_actividad_ejemplo(opcion_correcta_id="opc_1")
        posiciones_observadas = set()

        for _ in range(50):
            mezcladas = mezclar_opciones_actividad(act)
            pos = next(i for i, o in enumerate(mezcladas) if o.opcion_id == act.opcion_correcta_id)
            posiciones_observadas.add(pos)

        # En 50 repeticiones deben haberse observado al menos 2 posiciones diferentes (0, 1 o 2)
        self.assertGreater(len(posiciones_observadas), 1, "La posición debe variar y no ser siempre 0")

    def test_correccion_correcta_independiente_de_la_posicion_visible(self) -> None:
        """Verifica que la corrección sea correcta sin importar en qué posición (A, B o C) quedó la opción."""
        act = _crear_actividad_ejemplo(opcion_correcta_id="opc_1")

        # Simular que opc_1 quedó en la posición 2 (C)
        opciones_reordenadas = [act.opciones[1], act.opciones[2], act.opciones[0]]
        self.assertEqual(opciones_reordenadas[2].opcion_id, "opc_1")

        # El usuario elige opc_1 (que está en la posición C)
        res = validar_y_responder_actividad(self.usuario_valido, act, "opc_1")
        self.assertTrue(res.ok)
        self.assertEqual(res.valor.resultado, ResultadoIntento.CORRECTO)

        # Si elige la opción de la posición A (opc_2), es incorrecto
        res_error = validar_y_responder_actividad(self.usuario_valido, act, "opc_2")
        self.assertTrue(res_error.ok)
        self.assertEqual(res_error.valor.resultado, ResultadoIntento.INCORRECTO)

    def test_estabilidad_del_orden_durante_actualizaciones_en_sesion(self) -> None:
        """Verifica que el orden mezclado se conserve estable durante el intento en st.session_state."""
        act = _crear_actividad_ejemplo()
        ordenes: dict[UUID, list[Opcion]] = st.session_state.setdefault("cuestionario_orden_opciones", {})

        # Primera renderización
        orden_primera_vez = mezclar_opciones_actividad(act)
        ordenes[act.actividad_id] = orden_primera_vez

        # Simular reruns de Streamlit
        for _ in range(5):
            orden_recuperado = st.session_state.cuestionario_orden_opciones[act.actividad_id]
            self.assertEqual(
                [o.opcion_id for o in orden_recuperado],
                [o.opcion_id for o in orden_primera_vez],
                "El orden debe ser estable durante los reruns del mismo intento"
            )

    # =========================================================================
    # 3. Pruebas de Selección Inicial Vacía y Validación (Problema 1)
    # =========================================================================

    def test_validar_y_responder_rechaza_opcion_vacia_o_none(self) -> None:
        """Rechaza confirmación si no se seleccionó ninguna opción."""
        act = _crear_actividad_ejemplo()
        res_vacia = validar_y_responder_actividad(self.usuario_valido, act, "")
        self.assertFalse(res_vacia.ok)
        self.assertEqual(res_vacia.error.codigo, CODIGO_RESPUESTA_INVALIDA)

        res_espacios = validar_y_responder_actividad(self.usuario_valido, act, "   ")
        self.assertFalse(res_espacios.ok)
        self.assertEqual(res_espacios.error.codigo, CODIGO_RESPUESTA_INVALIDA)

    def test_validar_y_responder_rechaza_opcion_inexistente(self) -> None:
        """Rechaza opción manipulada que no pertenece a las 3 opciones legítimas."""
        act = _crear_actividad_ejemplo()
        res = validar_y_responder_actividad(
            usuario=self.usuario_valido,
            actividad=act,
            opcion_id="opcion_falsa_hack",
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.error.codigo, CODIGO_RESPUESTA_INVALIDA)

    def test_validar_y_responder_requiere_usuario_autenticado(self) -> None:
        """Rechaza la evaluación si el usuario es None o no es ContextoUsuario."""
        act = _crear_actividad_ejemplo()
        res = validar_y_responder_actividad(
            usuario=None,  # type: ignore
            actividad=act,
            opcion_id="opc_1",
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.error.codigo, CODIGO_SESION_REQUERIDA)

    # =========================================================================
    # 4. Pruebas de Gestión de Estado y Ciclo de Vida en Streamlit
    # =========================================================================

    def test_inicializar_estado_cuestionario(self) -> None:
        """Comprueba que las claves de sesión del cuestionario se inicialicen correctamente."""
        self.assertIn("cuestionario_indice_actual", st.session_state)
        self.assertEqual(st.session_state.cuestionario_indice_actual, 0)
        self.assertIn("cuestionario_respuestas", st.session_state)
        self.assertEqual(st.session_state.cuestionario_respuestas, {})
        self.assertIn("cuestionario_opciones_elegidas", st.session_state)
        self.assertEqual(st.session_state.cuestionario_opciones_elegidas, {})
        self.assertIn("cuestionario_orden_opciones", st.session_state)
        self.assertEqual(st.session_state.cuestionario_orden_opciones, {})
        self.assertIn("cuestionario_confirmado", st.session_state)
        self.assertFalse(st.session_state.cuestionario_confirmado)
        self.assertIn("cuestionario_finalizado", st.session_state)
        self.assertFalse(st.session_state.cuestionario_finalizado)

    def test_limpiar_datos_cuestionario_borra_ordenes_y_widgets(self) -> None:
        """Verifica que limpiar_datos_cuestionario restablezca respuestas, órdenes y widgets."""
        act_id = uuid4()
        st.session_state.cuestionario_indice_actual = 2
        st.session_state.cuestionario_respuestas = {
            act_id: ResultadoPractica(uuid4(), ResultadoIntento.CORRECTO, "Bien", False)
        }
        st.session_state.cuestionario_opciones_elegidas = {act_id: "opc_1"}
        st.session_state.cuestionario_orden_opciones = {act_id: [_crear_actividad_ejemplo().opciones]}
        st.session_state[f"radio_actividad_{act_id}"] = "A) A ceramic mug"
        st.session_state.cuestionario_confirmado = True
        st.session_state.cuestionario_exploracion_id = uuid4()
        st.session_state.cuestionario_finalizado = True

        limpiar_datos_cuestionario()

        self.assertEqual(st.session_state.cuestionario_indice_actual, 0)
        self.assertEqual(st.session_state.cuestionario_respuestas, {})
        self.assertEqual(st.session_state.cuestionario_opciones_elegidas, {})
        self.assertEqual(st.session_state.cuestionario_orden_opciones, {})
        self.assertNotIn(f"radio_actividad_{act_id}", st.session_state, "Los widgets deben reiniciarse")
        self.assertFalse(st.session_state.cuestionario_confirmado)
        self.assertIsNone(st.session_state.cuestionario_exploracion_id)
        self.assertFalse(st.session_state.cuestionario_finalizado)

    def test_limpieza_centralizada_al_descartar_o_cambiar_imagen(self) -> None:
        """Verifica que al descartar o cambiar imagen se limpien automáticamente los cuestionarios."""
        act_id = uuid4()
        st.session_state.cuestionario_indice_actual = 1
        st.session_state.cuestionario_respuestas = {
            act_id: ResultadoPractica(uuid4(), ResultadoIntento.CORRECTO, "Explicación", False)
        }
        st.session_state.cuestionario_confirmado = True

        limpiar_datos_exploracion()

        self.assertEqual(st.session_state.cuestionario_indice_actual, 0)
        self.assertEqual(st.session_state.cuestionario_respuestas, {})
        self.assertFalse(st.session_state.cuestionario_confirmado)

    def test_cerrar_sesion_limpia_cuestionario_y_aisla_usuarios(self) -> None:
        """Verifica que al cerrar sesión no queden respuestas ni progreso para el siguiente usuario."""
        act_id = uuid4()
        st.session_state.cuestionario_indice_actual = 3
        st.session_state.cuestionario_respuestas = {
            act_id: ResultadoPractica(uuid4(), ResultadoIntento.CORRECTO, "Ok", False)
        }
        st.session_state.cuestionario_finalizado = True

        cerrar_sesion_usuario()

        self.assertIsNone(st.session_state.usuario)
        self.assertEqual(st.session_state.cuestionario_indice_actual, 0)
        self.assertEqual(st.session_state.cuestionario_respuestas, {})
        self.assertFalse(st.session_state.cuestionario_finalizado)

    # =========================================================================
    # 5. Pruebas de Flujo Pedagógico: Cuestionarios de 1, 2 y 0 actividades
    # =========================================================================

    def test_flujo_cuestionario_una_actividad(self) -> None:
        """Simula el flujo completo de un cuestionario con una sola actividad."""
        act1 = _crear_actividad_ejemplo(opcion_correcta_id="opc_1")
        exp = Exploracion(
            exploracion_id=uuid4(),
            user_id=self.usuario_valido.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            actividades=[act1],
        )

        st.session_state.exploracion_actual = exp
        st.session_state.cuestionario_exploracion_id = exp.exploracion_id

        # 1. Inicio: Pregunta 0 sin responder
        self.assertEqual(st.session_state.cuestionario_indice_actual, 0)
        self.assertNotIn(act1.actividad_id, st.session_state.cuestionario_respuestas)

        # 2. Responder
        res = validar_y_responder_actividad(self.usuario_valido, act1, "opc_1")
        self.assertTrue(res.ok)
        st.session_state.cuestionario_respuestas[act1.actividad_id] = res.valor
        st.session_state.cuestionario_opciones_elegidas[act1.actividad_id] = "opc_1"
        st.session_state.cuestionario_confirmado = True

        # 3. Comprobar que al ser única actividad, finaliza
        es_ultima = (st.session_state.cuestionario_indice_actual + 1 >= len(exp.actividades))
        self.assertTrue(es_ultima)
        st.session_state.cuestionario_finalizado = True

        # Resumen: 1 de 1 aciertos
        total_aciertos = sum(1 for r in st.session_state.cuestionario_respuestas.values() if r.resultado == ResultadoIntento.CORRECTO)
        self.assertEqual(total_aciertos, 1)

    def test_flujo_cuestionario_dos_actividades_navegacion(self) -> None:
        """Simula navegación secuencial en un cuestionario de dos actividades."""
        act1 = _crear_actividad_ejemplo(opcion_correcta_id="opc_1")
        act2 = _crear_actividad_ejemplo(opcion_correcta_id="opc_2")
        exp = Exploracion(
            exploracion_id=uuid4(),
            user_id=self.usuario_valido.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            actividades=[act1, act2],
        )
        st.session_state.exploracion_actual = exp
        st.session_state.cuestionario_exploracion_id = exp.exploracion_id

        # Pregunta 1: responde incorrectamente
        res1 = validar_y_responder_actividad(self.usuario_valido, act1, "opc_2")
        self.assertEqual(res1.valor.resultado, ResultadoIntento.INCORRECTO)
        st.session_state.cuestionario_respuestas[act1.actividad_id] = res1.valor

        # Avanzar a Pregunta 2: el índice cambia y se desconfirma
        st.session_state.cuestionario_indice_actual += 1
        st.session_state.cuestionario_confirmado = False
        self.assertEqual(st.session_state.cuestionario_indice_actual, 1)
        self.assertFalse(st.session_state.cuestionario_confirmado)
        # La pregunta 2 no ha sido respondida aún
        self.assertNotIn(act2.actividad_id, st.session_state.cuestionario_respuestas)

        # Pregunta 2: responde correctamente
        res2 = validar_y_responder_actividad(self.usuario_valido, act2, "opc_2")
        self.assertEqual(res2.valor.resultado, ResultadoIntento.CORRECTO)
        st.session_state.cuestionario_respuestas[act2.actividad_id] = res2.valor

        # Avanzar a resumen
        st.session_state.cuestionario_finalizado = True
        total_aciertos = sum(1 for r in st.session_state.cuestionario_respuestas.values() if r.resultado == ResultadoIntento.CORRECTO)
        self.assertEqual(total_aciertos, 1)
        self.assertEqual(len(st.session_state.cuestionario_respuestas), 2)

    def test_exploracion_sin_actividades_no_falla(self) -> None:
        """Comprueba que una exploración utilizable pero sin actividades no genere excepciones."""
        exp = Exploracion(
            exploracion_id=uuid4(),
            user_id=self.usuario_valido.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            actividades=[],
        )
        st.session_state.exploracion_actual = exp
        self.assertEqual(len(st.session_state.exploracion_actual.actividades), 0)


if __name__ == "__main__":
    unittest.main()
