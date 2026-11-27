"""Pruebas automatizadas para el módulo M8: Consulta y Cálculo de Progreso (Parte 13).

Verifica:
1. Usuario sin actividad (resumen vacío válido, porcentajes en None).
2. Vocabulario repetido en varias exploraciones (con distintos `objeto_id`) y practicado varias veces,
   conservando una única entrada por palabra normalizada con estado `PRACTICADA` y la `ultima_practica` más reciente.
3. Intentos separados por tipo de actividad (`CUESTIONARIO` y `FIND_IT`) con porcentajes de aciertos exactos.
4. Desafíos de Find It del vocabulario base:
   - Si el usuario aún no exploró esa palabra, cuenta el intento en Find It sin añadir la palabra base a `palabras_exploradas`.
   - Si el usuario sí exploró esa palabra y luego hizo el desafío base, la palabra explorada pasa a `PRACTICADA`.
5. Conservación de `INDETERMINABLE` como resultado propio:
   - No marca la palabra como `PRACTICADA`.
   - No suma a `find_it_no_encontrados` (errores).
   - Se excluye del denominador del porcentaje de aciertos.
   - Si todos los intentos son `INDETERMINABLE` y no hay evaluables, los porcentajes de aciertos son `None`.
6. Función `obtener_progreso` / `consultar_progreso_usuario` conectada con `RepositorioSupabase`
   tanto en sesión autenticada como en modo demo, y propagación de errores cuando falla una consulta.
"""

from __future__ import annotations
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from homelens.datos.supabase import RepositorioSupabase
from homelens.errores import (
    CODIGO_PERSISTENCIA_FALLIDA,
    CODIGO_SESION_REQUERIDA,
    Resultado,
)
from homelens.modelos import (
    Actividad,
    ContextoUsuario,
    EstadoAnalisis,
    EstadoFindIt,
    EstadoPalabra,
    Exploracion,
    IntentoPractica,
    ObjetoEducativo,
    Opcion,
    RecuadroNormalizado,
    ResultadoIntento,
    TipoIntento,
    VerificacionFindIt,
)
from homelens.practicas import (
    construir_intento_cuestionario,
    construir_intento_find_it,
    obtener_desafios_find_it_disponibles,
    validar_y_responder_actividad,
)
from homelens.progreso import (
    calcular_progreso,
    consultar_progreso_usuario,
    obtener_progreso,
)
from tests.test_repositorio_supabase import MockSupabaseClient


class TestCalculoYConsultaProgresoParte13(unittest.TestCase):
    """Batería de pruebas unitarias e integración con repositorio para la Parte 13."""

    def setUp(self) -> None:
        self.user_id = UUID("11111111-1111-4111-8111-111111111111")
        self.usuario_auth = ContextoUsuario(
            user_id=self.user_id,
            sesion_id="jwt_token_valido_progreso",
            email="estudiante@homelens.edu",
            nombre="Estudiante Auth",
            es_demo=False,
        )
        self.usuario_demo = ContextoUsuario(
            user_id=UUID("00000000-0000-4000-8000-000000000001"),
            sesion_id="local_demo_session",
            email="demo@homelens.edu",
            nombre="Estudiante Demo",
            es_demo=True,
        )
        self.mock_client = MockSupabaseClient()
        self.repo_auth = RepositorioSupabase(
            supabase_url="https://test.supabase.co",
            anon_key="test_anon_key",
            cliente_supabase=self.mock_client,
        )
        self.almacen_exp_demo = {}
        self.almacen_int_demo = {}
        self.repo_demo = RepositorioSupabase(
            almacen_demo=self.almacen_exp_demo,
            almacen_intentos_demo=self.almacen_int_demo,
        )

    def _crear_objeto(
        self,
        nombre_en: str,
        nombre_es: str,
        exploracion_id: UUID | None = None,
        objeto_id: UUID | None = None,
    ) -> ObjetoEducativo:
        return ObjetoEducativo(
            objeto_id=objeto_id or uuid4(),
            exploracion_id=exploracion_id or uuid4(),
            nombre_en=nombre_en,
            nombre_es=nombre_es,
            recuadro=RecuadroNormalizado(ymin=100, xmin=100, ymax=400, xmax=400),
            frase_en=f"This is a {nombre_en.lower()}.",
            frase_es=f"Esto es {nombre_es.lower()}.",
        )

    def test_calcular_progreso_vacio(self) -> None:
        """Verifica que sin vocabulario ni intentos se devuelva un resumen vacío válido sin porcentajes inventados."""
        resumen = calcular_progreso([], [])
        self.assertEqual(resumen.total_intentos, 0)
        self.assertEqual(resumen.palabras_exploradas, [])
        self.assertEqual(resumen.palabras_practicadas, [])
        self.assertEqual(resumen.palabras_solo_exploradas, [])
        self.assertEqual(resumen.total_palabras_exploradas, 0)
        self.assertEqual(resumen.total_palabras_practicadas, 0)
        self.assertFalse(resumen.tiene_actividad)
        self.assertIsNone(resumen.porcentaje_aciertos_cuestionarios)
        self.assertIsNone(resumen.porcentaje_aciertos_find_it)
        self.assertIsNone(resumen.porcentaje_aciertos_global)
        self.assertEqual(resumen.resultados_por_tipo["cuestionarios_correctos"], 0)
        self.assertEqual(resumen.resultados_por_tipo["cuestionarios_incorrectos"], 0)
        self.assertEqual(resumen.resultados_por_tipo["find_it_encontrados"], 0)
        self.assertEqual(resumen.resultados_por_tipo["find_it_no_encontrados"], 0)
        self.assertEqual(resumen.resultados_por_tipo["find_it_indeterminables"], 0)

    def test_calcular_progreso_con_palabras_e_intentos_ambos_tipos(self) -> None:
        """Verifica la separación entre palabras exploradas/practicadas y resultados de Cuestionarios y Find It."""
        obj_lamp = self._crear_objeto("Lamp", "Lámpara")
        obj_chair = self._crear_objeto("Chair", "Silla")
        obj_table = self._crear_objeto("Table", "Mesa")

        t1 = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 20, 11, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)

        intentos = [
            IntentoPractica(
                intento_id=uuid4(),
                user_id=self.user_id,
                tipo=TipoIntento.CUESTIONARIO,
                fecha=t1,
                actividad_id=uuid4(),
                opcion_elegida_id="A",
                resultado=ResultadoIntento.CORRECTO,
                objeto_ids=[obj_lamp.objeto_id],
            ),
            IntentoPractica(
                intento_id=uuid4(),
                user_id=self.user_id,
                tipo=TipoIntento.CUESTIONARIO,
                fecha=t2,
                actividad_id=uuid4(),
                opcion_elegida_id="B",
                resultado=ResultadoIntento.INCORRECTO,
                objeto_ids=[obj_lamp.objeto_id],
            ),
            IntentoPractica(
                intento_id=uuid4(),
                user_id=self.user_id,
                tipo=TipoIntento.FIND_IT,
                fecha=t3,
                desafio_id=uuid4(),
                resultado=ResultadoIntento.CORRECTO,
                objeto_ids=[obj_chair.objeto_id],
            ),
        ]

        resumen = calcular_progreso([obj_lamp, obj_chair, obj_table], intentos)

        self.assertTrue(resumen.tiene_actividad)
        self.assertEqual(resumen.total_intentos, 3)
        self.assertEqual(resumen.total_palabras_exploradas, 3)
        self.assertEqual(resumen.total_palabras_practicadas, 2)
        self.assertEqual(len(resumen.palabras_solo_exploradas), 1)
        self.assertEqual(resumen.palabras_solo_exploradas[0].nombre_en, "Table")
        self.assertEqual(resumen.palabras_solo_exploradas[0].estado, EstadoPalabra.EXPLORADA)
        self.assertIsNone(resumen.palabras_solo_exploradas[0].ultima_practica)

        mapa_palabras = {p.nombre_en: p for p in resumen.palabras_exploradas}
        self.assertEqual(mapa_palabras["Lamp"].estado, EstadoPalabra.PRACTICADA)
        self.assertEqual(mapa_palabras["Lamp"].ultima_practica, t2)
        self.assertEqual(mapa_palabras["Chair"].estado, EstadoPalabra.PRACTICADA)
        self.assertEqual(mapa_palabras["Chair"].ultima_practica, t3)

        # Resultados por tipo: Cuestionarios (1/2 = 50%), Find It (1/1 = 100%), Global (2/3 = 66.67%)
        self.assertEqual(resumen.resultados_por_tipo["cuestionarios_correctos"], 1)
        self.assertEqual(resumen.resultados_por_tipo["cuestionarios_incorrectos"], 1)
        self.assertEqual(resumen.resultados_por_tipo["cuestionarios_total"], 2)
        self.assertEqual(resumen.porcentaje_aciertos_cuestionarios, 50.0)

        self.assertEqual(resumen.resultados_por_tipo["find_it_encontrados"], 1)
        self.assertEqual(resumen.resultados_por_tipo["find_it_no_encontrados"], 0)
        self.assertEqual(resumen.resultados_por_tipo["find_it_indeterminables"], 0)
        self.assertEqual(resumen.porcentaje_aciertos_find_it, 100.0)
        self.assertEqual(resumen.porcentaje_aciertos_global, 66.67)

    def test_vocabulario_repetido_en_varias_exploraciones_y_practicado_varias_veces(self) -> None:
        """Si una palabra aparece en varias exploraciones y se practica en la primera o segunda, se consolida una vez con la fecha más reciente."""
        exp_1_id = uuid4()
        exp_2_id = uuid4()
        mug_exp_1 = self._crear_objeto("Coffee Mug", "Taza de café", exploracion_id=exp_1_id)
        mug_exp_2 = self._crear_objeto("  coffee mug ", "Taza de café", exploracion_id=exp_2_id)

        exp_1 = Exploracion(
            exploracion_id=exp_1_id,
            user_id=self.user_id,
            creada_en=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[mug_exp_1],
            actividades=[],
        )
        exp_2 = Exploracion(
            exploracion_id=exp_2_id,
            user_id=self.user_id,
            creada_en=datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[mug_exp_2],
            actividades=[],
        )

        # Guardar ambas exploraciones en el repositorio
        self.assertTrue(self.repo_auth.guardar_exploracion(self.usuario_auth, exp_1).ok)
        self.assertTrue(self.repo_auth.guardar_exploracion(self.usuario_auth, exp_2).ok)

        # Practicar primero sobre mug_exp_1 (la exploración más antigua) y luego sobre mug_exp_2
        fecha_practica_1 = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)
        fecha_practica_2 = datetime(2026, 11, 18, 16, 30, tzinfo=timezone.utc)

        intento_1 = IntentoPractica(
            intento_id=uuid4(),
            user_id=self.user_id,
            tipo=TipoIntento.CUESTIONARIO,
            fecha=fecha_practica_1,
            actividad_id=uuid4(),
            opcion_elegida_id="A",
            resultado=ResultadoIntento.INCORRECTO,
            objeto_ids=[mug_exp_1.objeto_id],
        )
        self.assertTrue(self.repo_auth.guardar_intento(self.usuario_auth, intento_1).ok)

        # Aunque exista una exploración más nueva (exp_2) donde mug_exp_2 no fue practicada aún,
        # la palabra 'Coffee Mug' ya debe figurar como PRACTICADA gracias a mug_exp_1.
        res_1 = obtener_progreso(self.usuario_auth, repositorio=self.repo_auth)
        self.assertTrue(res_1.ok)
        self.assertEqual(len(res_1.valor.palabras_exploradas), 1)
        self.assertEqual(res_1.valor.palabras_exploradas[0].estado, EstadoPalabra.PRACTICADA)
        self.assertEqual(res_1.valor.palabras_exploradas[0].ultima_practica, fecha_practica_1)

        # Ahora se practica también sobre mug_exp_2 con fecha posterior: actualiza ultima_practica a la más reciente
        intento_2 = IntentoPractica(
            intento_id=uuid4(),
            user_id=self.user_id,
            tipo=TipoIntento.FIND_IT,
            fecha=fecha_practica_2,
            desafio_id=uuid4(),
            resultado=ResultadoIntento.CORRECTO,
            objeto_ids=[mug_exp_2.objeto_id],
        )
        self.assertTrue(self.repo_auth.guardar_intento(self.usuario_auth, intento_2).ok)

        res_2 = obtener_progreso(self.usuario_auth, repositorio=self.repo_auth)
        self.assertTrue(res_2.ok)
        self.assertEqual(len(res_2.valor.palabras_exploradas), 1)
        palabra = res_2.valor.palabras_exploradas[0]
        self.assertEqual(palabra.nombre_en, "coffee mug")
        self.assertEqual(palabra.estado, EstadoPalabra.PRACTICADA)
        self.assertEqual(palabra.ultima_practica, fecha_practica_2)
        self.assertEqual(res_2.valor.total_intentos, 2)

    def test_find_it_vocabulario_base_sin_explorar_y_explorado(self) -> None:
        """Comprueba cómo se comporta un intento Find It del vocabulario base antes y después de explorar esa palabra."""
        # 1. El usuario realiza un desafío Find It del vocabulario base ("Book") sin haber explorado fotos aún
        desafios_base = obtener_desafios_find_it_disponibles(self.usuario_auth, exploracion_actual=None)
        desafio_book = next(d for d in desafios_base if d.nombre_en == "Book")
        fecha_find_base = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)

        intento_base = construir_intento_find_it(
            usuario=self.usuario_auth,
            desafio=desafio_book,
            verificacion=VerificacionFindIt(EstadoFindIt.ENCONTRADO, "¡Encontraste el libro!"),
            fecha=fecha_find_base,
        )
        self.assertTrue(self.repo_auth.guardar_intento(self.usuario_auth, intento_base).ok)

        # Mientras no haya explorado "Book":
        # - No se agrega a palabras_exploradas (total_palabras_exploradas == 0)
        # - Sí se suma como palabra identificable practicada en total_palabras_practicadas (1) y palabras_practicadas
        res_sin_exp = obtener_progreso(self.usuario_auth, repositorio=self.repo_auth)
        self.assertTrue(res_sin_exp.ok)
        self.assertEqual(res_sin_exp.valor.palabras_exploradas, [])
        self.assertEqual(res_sin_exp.valor.total_palabras_exploradas, 0)
        self.assertEqual(res_sin_exp.valor.total_palabras_practicadas, 1)
        self.assertEqual(len(res_sin_exp.valor.palabras_practicadas), 1)
        self.assertEqual(res_sin_exp.valor.palabras_practicadas[0].nombre_en, "Book")
        self.assertEqual(res_sin_exp.valor.palabras_practicadas[0].estado, EstadoPalabra.PRACTICADA)
        self.assertEqual(res_sin_exp.valor.palabras_practicadas[0].ultima_practica, fecha_find_base)
        self.assertEqual(res_sin_exp.valor.total_intentos, 1)
        self.assertEqual(res_sin_exp.valor.resultados_por_tipo["find_it_encontrados"], 1)
        self.assertTrue(res_sin_exp.valor.tiene_actividad)

        # Si repite un segundo intento sobre el mismo desafío base "Book", no se duplica en total_palabras_practicadas
        fecha_find_base_2 = datetime(2026, 11, 22, 16, 0, tzinfo=timezone.utc)
        intento_base_2 = construir_intento_find_it(
            usuario=self.usuario_auth,
            desafio=desafio_book,
            verificacion=VerificacionFindIt(EstadoFindIt.NO_ENCONTRADO, "No se vio el libro."),
            fecha=fecha_find_base_2,
        )
        self.assertTrue(self.repo_auth.guardar_intento(self.usuario_auth, intento_base_2).ok)
        res_rep_base = obtener_progreso(self.usuario_auth, repositorio=self.repo_auth)
        self.assertEqual(res_rep_base.valor.total_palabras_exploradas, 0)
        self.assertEqual(res_rep_base.valor.total_palabras_practicadas, 1)
        self.assertEqual(res_rep_base.valor.palabras_practicadas[0].ultima_practica, fecha_find_base_2)

        # 2. Si el usuario explora "Book" en una fotografía y la guarda, pasa a palabras_exploradas como PRACTICADA
        #    y total_palabras_practicadas sigue siendo 1 (sin duplicar entre exploradas y base)
        exp_id = uuid4()
        obj_book = self._crear_objeto("Book", "Libro", exploracion_id=exp_id)
        exp = Exploracion(
            exploracion_id=exp_id,
            user_id=self.user_id,
            creada_en=datetime(2026, 11, 22, 14, 0, tzinfo=timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[obj_book],
        )
        self.assertTrue(self.repo_auth.guardar_exploracion(self.usuario_auth, exp).ok)

        res_con_exp = obtener_progreso(self.usuario_auth, repositorio=self.repo_auth)
        self.assertTrue(res_con_exp.ok)
        self.assertEqual(res_con_exp.valor.total_palabras_exploradas, 1)
        self.assertEqual(res_con_exp.valor.total_palabras_practicadas, 1)
        self.assertEqual(len(res_con_exp.valor.palabras_practicadas), 1)
        self.assertEqual(res_con_exp.valor.palabras_exploradas[0].nombre_en, "Book")
        self.assertEqual(res_con_exp.valor.palabras_exploradas[0].estado, EstadoPalabra.PRACTICADA)
        self.assertEqual(res_con_exp.valor.palabras_exploradas[0].ultima_practica, fecha_find_base_2)

    def test_intento_cuestionario_de_exploracion_no_guardada_conserva_estadisticas(self) -> None:
        """Si un cuestionario se respondió sobre una exploración no guardada, solo queda el UUID y se mantiene en estadísticas."""
        id_objeto_no_guardado = uuid4()
        intento_huerfano = IntentoPractica(
            intento_id=uuid4(),
            user_id=self.user_id,
            tipo=TipoIntento.CUESTIONARIO,
            fecha=datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc),
            actividad_id=uuid4(),
            opcion_elegida_id="A",
            resultado=ResultadoIntento.CORRECTO,
            objeto_ids=[id_objeto_no_guardado],
        )
        resumen = calcular_progreso([], [intento_huerfano])
        self.assertEqual(resumen.total_intentos, 1)
        self.assertEqual(resumen.resultados_por_tipo["cuestionarios_correctos"], 1)
        self.assertEqual(resumen.porcentaje_aciertos_cuestionarios, 100.0)
        self.assertEqual(resumen.total_palabras_exploradas, 0)
        self.assertEqual(resumen.total_palabras_practicadas, 0)
        self.assertEqual(resumen.resultados_por_tipo["objetos_no_resueltos_count"], 1)

    def test_indeterminable_excluido_de_errores_denominador_y_caso_todos_indeterminables(self) -> None:
        """Verifica que INDETERMINABLE no cuente como error, no marque palabra como practicada y no entre al denominador."""
        obj_keys = self._crear_objeto("Keys", "Llaves")
        fecha_indet = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)

        intento_indet_1 = IntentoPractica(
            intento_id=uuid4(),
            user_id=self.user_id,
            tipo=TipoIntento.FIND_IT,
            fecha=fecha_indet,
            desafio_id=uuid4(),
            resultado=ResultadoIntento.INDETERMINABLE,
            objeto_ids=[obj_keys.objeto_id],
        )
        intento_indet_2 = IntentoPractica(
            intento_id=uuid4(),
            user_id=self.user_id,
            tipo=TipoIntento.FIND_IT,
            fecha=fecha_indet,
            desafio_id=uuid4(),
            resultado=ResultadoIntento.INDETERMINABLE,
            objeto_ids=[obj_keys.objeto_id],
        )

        # Caso 1: TODOS los intentos son INDETERMINABLE y no hay intentos evaluables
        resumen_solo_indet = calcular_progreso([obj_keys], [intento_indet_1, intento_indet_2])
        self.assertEqual(resumen_solo_indet.total_intentos, 2)
        self.assertEqual(resumen_solo_indet.resultados_por_tipo["find_it_indeterminables"], 2)
        self.assertEqual(resumen_solo_indet.resultados_por_tipo["find_it_no_encontrados"], 0)
        self.assertEqual(resumen_solo_indet.resultados_por_tipo["find_it_encontrados"], 0)
        self.assertEqual(resumen_solo_indet.resultados_por_tipo["find_it_evaluables"], 0)
        self.assertEqual(resumen_solo_indet.resultados_por_tipo["total_evaluables"], 0)

        # Sin intentos evaluables, los porcentajes deben ser None (ni 0% ni 100%)
        self.assertIsNone(resumen_solo_indet.porcentaje_aciertos_find_it)
        self.assertIsNone(resumen_solo_indet.porcentaje_aciertos_cuestionarios)
        self.assertIsNone(resumen_solo_indet.porcentaje_aciertos_global)

        # Y la palabra permanece EXPLORADA (no PRACTICADA)
        self.assertEqual(resumen_solo_indet.palabras_exploradas[0].estado, EstadoPalabra.EXPLORADA)
        self.assertIsNone(resumen_solo_indet.palabras_exploradas[0].ultima_practica)

        # Caso 2: 1 ENCONTRADO, 1 NO_ENCONTRADO y 2 INDETERMINABLES -> denominador evaluable es 2 (50.0%, no 25%)
        intento_ok = IntentoPractica(
            intento_id=uuid4(),
            user_id=self.user_id,
            tipo=TipoIntento.FIND_IT,
            fecha=fecha_indet,
            desafio_id=uuid4(),
            resultado=ResultadoIntento.CORRECTO,
            objeto_ids=[obj_keys.objeto_id],
        )
        intento_fail = IntentoPractica(
            intento_id=uuid4(),
            user_id=self.user_id,
            tipo=TipoIntento.FIND_IT,
            fecha=fecha_indet,
            desafio_id=uuid4(),
            resultado=ResultadoIntento.INCORRECTO,
            objeto_ids=[obj_keys.objeto_id],
        )
        resumen_mixto = calcular_progreso(
            [obj_keys],
            [intento_indet_1, intento_indet_2, intento_ok, intento_fail],
        )
        self.assertEqual(resumen_mixto.total_intentos, 4)
        self.assertEqual(resumen_mixto.resultados_por_tipo["find_it_total"], 4)
        self.assertEqual(resumen_mixto.resultados_por_tipo["find_it_evaluables"], 2)
        self.assertEqual(resumen_mixto.resultados_por_tipo["find_it_indeterminables"], 2)
        self.assertEqual(resumen_mixto.resultados_por_tipo["find_it_no_encontrados"], 1)
        self.assertEqual(resumen_mixto.porcentaje_aciertos_find_it, 50.0)
        self.assertEqual(resumen_mixto.porcentaje_aciertos_global, 50.0)
        self.assertEqual(resumen_mixto.palabras_exploradas[0].estado, EstadoPalabra.PRACTICADA)

    def test_obtener_progreso_usuario_sin_actividad_y_modo_demo(self) -> None:
        """Verifica que obtener_progreso / consultar_progreso_usuario funcione tanto en sesión autenticada como en modo demo."""
        # 1. Usuario autenticado sin actividad en Supabase
        res_vacio_auth = consultar_progreso_usuario(self.usuario_auth, repositorio=self.repo_auth)
        self.assertTrue(res_vacio_auth.ok)
        self.assertFalse(res_vacio_auth.valor.tiene_actividad)
        self.assertEqual(res_vacio_auth.valor.total_intentos, 0)
        self.assertEqual(res_vacio_auth.valor.palabras_exploradas, [])

        # 2. Usuario en modo demo con exploración e intento guardados en memoria de sesión
        exp_demo_id = uuid4()
        obj_spoon = self._crear_objeto("Spoon", "Cuchara", exploracion_id=exp_demo_id)
        act_spoon = Actividad(
            actividad_id=uuid4(),
            exploracion_id=exp_demo_id,
            objeto_ids=[obj_spoon.objeto_id],
            pregunta="What do you use to eat soup?",
            opciones=[
                Opcion("A", "A spoon"),
                Opcion("B", "A fork"),
                Opcion("C", "A plate"),
            ],
            opcion_correcta_id="A",
            explicacion="A spoon is used for soup.",
        )
        exp_demo = Exploracion(
            exploracion_id=exp_demo_id,
            user_id=self.usuario_demo.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[obj_spoon],
            actividades=[act_spoon],
        )
        self.assertTrue(self.repo_demo.guardar_exploracion(self.usuario_demo, exp_demo).ok)

        res_eval = validar_y_responder_actividad(self.usuario_demo, act_spoon, "A")
        intento_demo = construir_intento_cuestionario(
            usuario=self.usuario_demo,
            actividad=act_spoon,
            opcion_elegida_id="A",
            resultado_practica=res_eval.valor,
        )
        self.assertTrue(self.repo_demo.guardar_intento(self.usuario_demo, intento_demo).ok)

        res_demo = consultar_progreso_usuario(self.usuario_demo, repositorio=self.repo_demo)
        self.assertTrue(res_demo.ok)
        self.assertTrue(res_demo.valor.tiene_actividad)
        self.assertEqual(res_demo.valor.total_palabras_exploradas, 1)
        self.assertEqual(res_demo.valor.total_palabras_practicadas, 1)
        self.assertEqual(res_demo.valor.porcentaje_aciertos_cuestionarios, 100.0)

    def test_obtener_progreso_propaga_errores_de_consulta_y_sesion(self) -> None:
        """Si falla listar_vocabulario, listar_intentos o no hay sesión válida, propaga el error controlado."""
        # 1. Sin usuario válido
        res_sin_usuario = obtener_progreso(None, repositorio=self.repo_auth)  # type: ignore[arg-type]
        self.assertFalse(res_sin_usuario.ok)
        self.assertEqual(res_sin_usuario.error.codigo, CODIGO_SESION_REQUERIDA)

        # 2. Fallo al consultar vocabulario
        repo_falla_vocab = MagicMock()
        repo_falla_vocab.listar_vocabulario.return_value = Resultado.fallo(
            codigo=CODIGO_PERSISTENCIA_FALLIDA,
            mensaje_usuario="Error simulado al consultar vocabulario.",
            reintentable=True,
        )
        res_err_vocab = obtener_progreso(self.usuario_auth, repositorio=repo_falla_vocab)
        self.assertFalse(res_err_vocab.ok)
        self.assertEqual(res_err_vocab.error.codigo, CODIGO_PERSISTENCIA_FALLIDA)
        self.assertIn("vocabulario", res_err_vocab.error.mensaje_usuario)
        repo_falla_vocab.listar_intentos.assert_not_called()

        # 3. Vocabulario exitoso pero fallo al consultar intentos
        repo_falla_intentos = MagicMock()
        repo_falla_intentos.listar_vocabulario.return_value = Resultado.exito([])
        repo_falla_intentos.listar_intentos.return_value = Resultado.fallo(
            codigo=CODIGO_PERSISTENCIA_FALLIDA,
            mensaje_usuario="Error simulado al consultar intentos.",
            reintentable=True,
        )
        res_err_intentos = obtener_progreso(self.usuario_auth, repositorio=repo_falla_intentos)
        self.assertFalse(res_err_intentos.ok)
        self.assertEqual(res_err_intentos.error.codigo, CODIGO_PERSISTENCIA_FALLIDA)
        self.assertIn("intentos", res_err_intentos.error.mensaje_usuario)


if __name__ == "__main__":
    unittest.main()
