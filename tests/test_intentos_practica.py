"""Pruebas automatizadas para la Parte 10: Registro y Repaso de Intentos de Práctica.

Verifica:
1. Guardado y recuperación de intentos de CUESTIONARIO y FIND_IT en Supabase simulado y modo demo.
2. Orden descendente por fecha (más recientes primero) y filtro opcional `desde`.
3. Aislamiento estricto entre usuarios (RLS + validación de user_id en servidor).
4. Prevención de duplicados ante doble clic o llamadas repetidas con el mismo `intento_id`.
5. Conservación de `ResultadoIntento.INDETERMINABLE` como estado propio.
6. Persistencia de desafíos Find It provenientes tanto de una exploración activa como del vocabulario base.
7. Flujo en Cuestionarios y Find It: reintento de guardado tras un fallo conservando el resultado visible
   y el mismo `intento_id` sin volver a corregir el cuestionario ni llamar otra vez a Gemini,
   y generación de un nuevo `intento_id` cuando el usuario inicia un intento nuevo.
8. Validación estática de la migración SQL `sql/migracion_tarea_10_intentos_practica.sql`.
"""

from __future__ import annotations
import io
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock
from uuid import UUID, uuid4
from PIL import Image
import streamlit as st
from streamlit.testing.v1 import AppTest

from homelens.config import Configuracion
from homelens.datos.supabase import RepositorioSupabase
from homelens.errores import (
    CODIGO_ACCESO_DENEGADO,
    CODIGO_PERSISTENCIA_FALLIDA,
    CODIGO_SESION_REQUERIDA,
    Resultado,
)
from homelens.modelos import (
    Actividad,
    ContextoUsuario,
    DesafioFindIt,
    EstadoAnalisis,
    EstadoFindIt,
    Exploracion,
    ImagenPreparada,
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
from homelens.progreso import calcular_progreso
from homelens.ui.cuestionarios import (
    guardar_intentos_cuestionario_finalizado,
    renderizar_pantalla_cuestionarios,
)
from homelens.ui.estado import (
    cerrar_sesion_usuario,
    inicializar_estado_sesion,
    limpiar_datos_cuestionario,
)
from homelens.ui.find_it import (
    guardar_intento_actual_find_it,
    renderizar_pantalla_find_it,
)
from tests.test_repositorio_supabase import MockSupabaseClient


RUTA_MIGRACION_TAREA_10 = (
    Path(__file__).resolve().parent.parent / "sql" / "migracion_tarea_10_intentos_practica.sql"
)


class TestRepositorioIntentosPractica(unittest.TestCase):
    """Pruebas del repositorio de Supabase para guardar_intento y listar_intentos."""

    def setUp(self) -> None:
        self.user_a_id = UUID("11111111-1111-4111-8111-111111111111")
        self.user_b_id = UUID("22222222-2222-4222-8222-222222222222")

        self.usuario_a = ContextoUsuario(
            user_id=self.user_a_id,
            sesion_id="jwt_valido_usuario_a",
            email="alumno.a@homelens.edu",
            nombre="Alumno A",
            es_demo=False,
        )
        self.usuario_b = ContextoUsuario(
            user_id=self.user_b_id,
            sesion_id="jwt_valido_usuario_b",
            email="alumno.b@homelens.edu",
            nombre="Alumno B",
            es_demo=False,
        )
        self.usuario_demo = ContextoUsuario(
            user_id=UUID("00000000-0000-4000-8000-000000000001"),
            sesion_id="local_demo_session",
            email="demo@homelens.edu",
            nombre="Demo",
            es_demo=True,
        )

        self.mock_client = MockSupabaseClient()
        self.repo = RepositorioSupabase(
            supabase_url="https://test.supabase.co",
            anon_key="test_anon_key",
            cliente_supabase=self.mock_client,
        )

        self.exp_id = uuid4()
        self.obj_exp = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=self.exp_id,
            nombre_en="Teapot",
            nombre_es="Tetera",
            recuadro=RecuadroNormalizado(100, 120, 450, 520),
            frase_en="The teapot is hot.",
            frase_es="La tetera está caliente.",
        )
        self.actividad = Actividad(
            actividad_id=uuid4(),
            exploracion_id=self.exp_id,
            objeto_ids=[self.obj_exp.objeto_id],
            pregunta="Which object holds hot tea?",
            opciones=[
                Opcion(opcion_id="A", texto="A teapot"),
                Opcion(opcion_id="B", texto="A pillow"),
                Opcion(opcion_id="C", texto="A shoe"),
            ],
            opcion_correcta_id="A",
            explicacion="A teapot is used to brew and serve hot tea.",
        )
        self.exploracion = Exploracion(
            exploracion_id=self.exp_id,
            user_id=self.user_a_id,
            creada_en=datetime(2026, 11, 20, 14, 0, tzinfo=timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[self.obj_exp],
            actividades=[self.actividad],
        )

    def test_guardar_y_listar_cuestionario_y_find_it_orden_mas_recientes_primero(self) -> None:
        """Guarda intentos de Cuestionario y Find It y los recupera con los más recientes primero."""
        t1 = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 25, 10, 5, tzinfo=timezone.utc)
        t3 = datetime(2026, 11, 25, 10, 10, tzinfo=timezone.utc)

        res_eval = validar_y_responder_actividad(self.usuario_a, self.actividad, "A", intento_id=uuid4())
        self.assertTrue(res_eval.ok)
        intento_quiz = construir_intento_cuestionario(
            usuario=self.usuario_a,
            actividad=self.actividad,
            opcion_elegida_id="A",
            resultado_practica=res_eval.valor,
            fecha=t1,
        )

        desafios = obtener_desafios_find_it_disponibles(self.usuario_a, self.exploracion)
        desafio_exploracion = desafios[0]  # Teapot (proveniente de la exploración)
        desafio_base = desafios[1]         # Coffee Mug (proveniente del vocabulario base)
        self.assertEqual(desafio_exploracion.objeto_origen_id, self.obj_exp.objeto_id)
        self.assertNotEqual(desafio_base.objeto_origen_id, self.obj_exp.objeto_id)

        intento_find_exp = construir_intento_find_it(
            usuario=self.usuario_a,
            desafio=desafio_exploracion,
            verificacion=VerificacionFindIt(EstadoFindIt.ENCONTRADO, "¡Encontraste la tetera!"),
            fecha=t2,
        )
        intento_find_base = construir_intento_find_it(
            usuario=self.usuario_a,
            desafio=desafio_base,
            verificacion=VerificacionFindIt(EstadoFindIt.NO_ENCONTRADO, "No se encontró la taza."),
            fecha=t3,
        )

        for it in (intento_quiz, intento_find_exp, intento_find_base):
            res_g = self.repo.guardar_intento(self.usuario_a, it)
            self.assertTrue(res_g.ok)
            self.assertEqual(res_g.valor.operacion_id, it.intento_id)

        res_lista = self.repo.listar_intentos(self.usuario_a)
        self.assertTrue(res_lista.ok)
        lista = res_lista.valor
        self.assertEqual(len(lista), 3)

        # Ordenados del más reciente (t3) al más antiguo (t1)
        self.assertEqual(
            [it.intento_id for it in lista],
            [intento_find_base.intento_id, intento_find_exp.intento_id, intento_quiz.intento_id],
        )

        # Verificar integridad de campos reconstruidos
        rec_base, rec_exp, rec_quiz = lista
        self.assertEqual(rec_base.tipo, TipoIntento.FIND_IT)
        self.assertEqual(rec_base.desafio_id, desafio_base.desafio_id)
        self.assertEqual(rec_base.objeto_ids, [desafio_base.objeto_origen_id])
        self.assertEqual(rec_base.resultado, ResultadoIntento.INCORRECTO)

        self.assertEqual(rec_exp.tipo, TipoIntento.FIND_IT)
        self.assertEqual(rec_exp.desafio_id, desafio_exploracion.desafio_id)
        self.assertEqual(rec_exp.objeto_ids, [self.obj_exp.objeto_id])
        self.assertEqual(rec_exp.resultado, ResultadoIntento.CORRECTO)

        self.assertEqual(rec_quiz.tipo, TipoIntento.CUESTIONARIO)
        self.assertEqual(rec_quiz.actividad_id, self.actividad.actividad_id)
        self.assertEqual(rec_quiz.opcion_elegida_id, "A")
        self.assertEqual(rec_quiz.resultado, ResultadoIntento.CORRECTO)
        self.assertEqual(rec_quiz.objeto_ids, [self.obj_exp.objeto_id])

        # Filtro opcional `desde`
        res_desde = self.repo.listar_intentos(self.usuario_a, desde=t2)
        self.assertTrue(res_desde.ok)
        self.assertEqual(
            [it.intento_id for it in res_desde.valor],
            [intento_find_base.intento_id, intento_find_exp.intento_id],
        )

    def test_conservacion_de_indeterminable_como_resultado_propio(self) -> None:
        """Verifica que INDETERMINABLE se guarde y recupere intacto y sea compatible con calcular_progreso."""
        desafio = obtener_desafios_find_it_disponibles(self.usuario_a, self.exploracion)[0]
        intento_indet = construir_intento_find_it(
            usuario=self.usuario_a,
            desafio=desafio,
            verificacion=VerificacionFindIt(
                estado=EstadoFindIt.INDETERMINABLE,
                mensaje="Imagen fuera de foco.",
            ),
        )
        self.assertEqual(intento_indet.resultado, ResultadoIntento.INDETERMINABLE)

        res_g = self.repo.guardar_intento(self.usuario_a, intento_indet)
        self.assertTrue(res_g.ok)

        res_l = self.repo.listar_intentos(self.usuario_a)
        self.assertTrue(res_l.ok)
        self.assertEqual(len(res_l.valor), 1)
        recuperado = res_l.valor[0]
        self.assertEqual(recuperado.resultado, ResultadoIntento.INDETERMINABLE)
        self.assertNotEqual(recuperado.resultado, ResultadoIntento.INCORRECTO)

        # Compatibilidad directa con calcular_progreso (Parte 13)
        resumen = calcular_progreso([self.obj_exp], res_l.valor)
        self.assertEqual(resumen.total_intentos, 1)
        self.assertEqual(resumen.resultados_por_tipo["find_it_indeterminables"], 1)
        self.assertEqual(resumen.resultados_por_tipo["find_it_no_encontrados"], 0)

    def test_idempotencia_doble_clic_mismo_intento_id_deja_un_solo_registro(self) -> None:
        """Un doble clic o reintento de guardado con el mismo intento_id no duplica filas y retorna éxito."""
        desafio = obtener_desafios_find_it_disponibles(self.usuario_a, None)[0]
        intento = construir_intento_find_it(
            usuario=self.usuario_a,
            desafio=desafio,
            verificacion=VerificacionFindIt(EstadoFindIt.ENCONTRADO, "Encontrado"),
        )

        res1 = self.repo.guardar_intento(self.usuario_a, intento)
        res2 = self.repo.guardar_intento(self.usuario_a, intento)

        self.assertTrue(res1.ok)
        self.assertTrue(res2.ok)
        self.assertEqual(res1.valor.operacion_id, intento.intento_id)
        self.assertEqual(res2.valor.operacion_id, intento.intento_id)

        filas_bd = self.mock_client.db.get("intentos_practica", [])
        self.assertEqual(len(filas_bd), 1)

        # También en modo demostración
        almacen_intentos_demo: Dict[UUID, IntentoPractica] = {}
        repo_demo = RepositorioSupabase(almacen_intentos_demo=almacen_intentos_demo)
        intento_demo = construir_intento_find_it(
            usuario=self.usuario_demo,
            desafio=obtener_desafios_find_it_disponibles(self.usuario_demo, None)[0],
            verificacion=VerificacionFindIt(EstadoFindIt.ENCONTRADO, "Demo"),
        )
        self.assertTrue(repo_demo.guardar_intento(self.usuario_demo, intento_demo).ok)
        self.assertTrue(repo_demo.guardar_intento(self.usuario_demo, intento_demo).ok)
        self.assertEqual(len(almacen_intentos_demo), 1)

    def test_aislamiento_estricto_entre_usuarios(self) -> None:
        """Cada usuario solo puede guardar y consultar sus propios intentos."""
        desafio_a = obtener_desafios_find_it_disponibles(self.usuario_a, None)[0]
        intento_a = construir_intento_find_it(
            usuario=self.usuario_a,
            desafio=desafio_a,
            verificacion=VerificacionFindIt(EstadoFindIt.ENCONTRADO, "OK A"),
        )

        # Usuario B no puede guardar un intento perteneciente a Usuario A
        res_cruzado = self.repo.guardar_intento(self.usuario_b, intento_a)
        self.assertFalse(res_cruzado.ok)
        self.assertEqual(res_cruzado.error.codigo, CODIGO_ACCESO_DENEGADO)

        # Usuario A guarda su intento
        self.assertTrue(self.repo.guardar_intento(self.usuario_a, intento_a).ok)

        # Usuario B consulta sus propios intentos: no ve los de A
        res_lista_b = self.repo.listar_intentos(self.usuario_b)
        self.assertTrue(res_lista_b.ok)
        self.assertEqual(res_lista_b.valor, [])

        # Usuario A consulta sus propios intentos: recibe exactamente el suyo
        res_lista_a = self.repo.listar_intentos(self.usuario_a)
        self.assertTrue(res_lista_a.ok)
        self.assertEqual(len(res_lista_a.valor), 1)
        self.assertEqual(res_lista_a.valor[0].intento_id, intento_a.intento_id)

        # Sin sesión válida se rechaza
        self.assertEqual(
            self.repo.guardar_intento(None, intento_a).error.codigo,  # type: ignore[arg-type]
            CODIGO_SESION_REQUERIDA,
        )
        self.assertEqual(
            self.repo.listar_intentos(None).error.codigo,  # type: ignore[arg-type]
            CODIGO_SESION_REQUERIDA,
        )


class TestFlujoGuardadoReintentoYRepasoUI(unittest.TestCase):
    """Pruebas del flujo de guardado, reintento tras fallo y repaso en Cuestionarios y Find It."""

    def setUp(self) -> None:
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        inicializar_estado_sesion()

        self.usuario = ContextoUsuario(
            user_id=UUID("33333333-3333-4333-8333-333333333333"),
            sesion_id="jwt_estudiante_test",
            email="estudiante@homelens.edu",
            nombre="Estudiante",
            es_demo=False,
        )
        st.session_state.usuario = self.usuario

        self.mock_client = MockSupabaseClient()
        self.repo = RepositorioSupabase(
            supabase_url="https://test.supabase.co",
            anon_key="test_anon_key",
            cliente_supabase=self.mock_client,
        )

        self.exp_id = uuid4()
        self.obj = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=self.exp_id,
            nombre_en="Lamp",
            nombre_es="Lámpara",
            recuadro=RecuadroNormalizado(50, 50, 400, 400),
            frase_en="The lamp is bright.",
            frase_es="La lámpara es brillante.",
        )
        self.act = Actividad(
            actividad_id=uuid4(),
            exploracion_id=self.exp_id,
            objeto_ids=[self.obj.objeto_id],
            pregunta="What gives light on the desk?",
            opciones=[
                Opcion("opc_1", "A lamp"),
                Opcion("opc_2", "A book"),
                Opcion("opc_3", "A rug"),
            ],
            opcion_correcta_id="opc_1",
            explicacion="A lamp provides light.",
        )
        self.exploracion = Exploracion(
            exploracion_id=self.exp_id,
            user_id=self.usuario.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[self.obj],
            actividades=[self.act],
        )

    def test_cuestionario_fallo_guardado_conserva_resultado_y_reintenta_con_mismo_id(self) -> None:
        """Si falla el guardado al finalizar un cuestionario, conserva el resultado y reintenta con el mismo ID sin reevaluar."""
        st.session_state.exploracion_actual = self.exploracion
        st.session_state.cuestionario_exploracion_id = self.exploracion.exploracion_id

        res_eval = validar_y_responder_actividad(
            usuario=self.usuario,
            actividad=self.act,
            opcion_id="opc_1",
            intento_id=uuid4(),
        )
        self.assertTrue(res_eval.ok)
        id_original = res_eval.valor.intento_id

        st.session_state.cuestionario_respuestas[self.act.actividad_id] = res_eval.valor
        st.session_state.cuestionario_opciones_elegidas[self.act.actividad_id] = "opc_1"
        st.session_state.cuestionario_intentos[self.act.actividad_id] = construir_intento_cuestionario(
            usuario=self.usuario,
            actividad=self.act,
            opcion_elegida_id="opc_1",
            resultado_practica=res_eval.valor,
        )
        st.session_state.cuestionario_finalizado = True

        # 1. Simular fallo de red al guardar
        self.mock_client.fallar_conexion = True
        exito_1 = guardar_intentos_cuestionario_finalizado(
            usuario=self.usuario,
            actividades=[self.act],
            repositorio=self.repo,
        )
        self.assertFalse(exito_1)
        self.assertIsNotNone(st.session_state.cuestionario_error_guardado)

        # El resultado sigue visible y conserva exactamente el mismo intento_id
        res_visible = st.session_state.cuestionario_respuestas[self.act.actividad_id]
        self.assertEqual(res_visible.resultado, ResultadoIntento.CORRECTO)
        self.assertEqual(res_visible.intento_id, id_original)
        self.assertFalse(res_visible.registrado)

        # 2. Restablecer conexión y reintentar guardado (más un segundo clic idempotente)
        self.mock_client.fallar_conexion = False
        exito_2 = guardar_intentos_cuestionario_finalizado(
            usuario=self.usuario,
            actividades=[self.act],
            repositorio=self.repo,
        )
        exito_3 = guardar_intentos_cuestionario_finalizado(
            usuario=self.usuario,
            actividades=[self.act],
            repositorio=self.repo,
        )
        self.assertTrue(exito_2)
        self.assertTrue(exito_3)
        self.assertIsNone(st.session_state.cuestionario_error_guardado)
        self.assertTrue(st.session_state.cuestionario_respuestas[self.act.actividad_id].registrado)

        # Debe existir un único registro en la BD con el id_original
        intentos_bd = self.repo.listar_intentos(self.usuario).valor
        self.assertEqual(len(intentos_bd), 1)
        self.assertEqual(intentos_bd[0].intento_id, id_original)

        # 3. Un intento nuevo iniciado por el usuario al reiniciar el cuestionario tiene un ID nuevo
        limpiar_datos_cuestionario()
        res_nuevo = validar_y_responder_actividad(
            usuario=self.usuario,
            actividad=self.act,
            opcion_id="opc_2",
            intento_id=uuid4(),
        )
        self.assertNotEqual(res_nuevo.valor.intento_id, id_original)
        st.session_state.cuestionario_respuestas[self.act.actividad_id] = res_nuevo.valor
        st.session_state.cuestionario_opciones_elegidas[self.act.actividad_id] = "opc_2"
        self.assertTrue(
            guardar_intentos_cuestionario_finalizado(self.usuario, [self.act], self.repo)
        )
        intentos_bd_2 = self.repo.listar_intentos(self.usuario).valor
        self.assertEqual(len(intentos_bd_2), 2)
        self.assertEqual(
            {it.intento_id for it in intentos_bd_2},
            {id_original, res_nuevo.valor.intento_id},
        )

    def test_find_it_fallo_guardado_y_reintento_sin_llamar_otra_vez_a_gemini(self) -> None:
        """En Find It, si el guardado falla, reintentar guarda el mismo intento_id sin volver a llamar a Gemini."""
        codigo = """
import io
from uuid import UUID, uuid4
from PIL import Image
import streamlit as st

from homelens.config import Configuracion
from homelens.datos.supabase import RepositorioSupabase
from homelens.errores import Resultado
from homelens.imagenes import preparar_imagen
from homelens.modelos import ContextoUsuario, EstadoFindIt, VerificacionFindIt
from homelens.ui.estado import inicializar_estado_sesion
from homelens.ui.find_it import renderizar_pantalla_find_it
from tests.test_repositorio_supabase import MockSupabaseClient

inicializar_estado_sesion()
if st.session_state.get("usuario") is None:
    st.session_state.usuario = ContextoUsuario(
        user_id=UUID("44444444-4444-4444-8444-444444444444"),
        sesion_id="jwt_find_it_test",
        nombre="Estudiante Find It",
        es_demo=False,
    )
if "mock_client" not in st.session_state:
    st.session_state.mock_client = MockSupabaseClient()
if "llamadas_gemini" not in st.session_state:
    st.session_state.llamadas_gemini = 0

repo = RepositorioSupabase(
    supabase_url="https://test.supabase.co",
    anon_key="test_anon_key",
    cliente_supabase=st.session_state.mock_client,
)

cfg = Configuracion(
    app_env="development",
    debug=True,
    log_level="INFO",
    app_port=8501,
    gemini_api_key="test-key",
    gemini_model="gemini-2.5-flash",
    gemini_timeout_seconds=30.0,
    gemini_max_retries=0,
    supabase_url="https://test.supabase.co",
    supabase_anon_key="test_anon_key",
    supabase_service_role_key=None,
    google_tts_language_code="en-US",
    google_tts_voice_name="en-US-Standard-C",
    max_image_size_bytes=5_000_000,
    audio_cache_ttl_seconds=3600,
    rate_limit_exploraciones_por_minuto=10,
)

def _verificar_contado(usuario, imagen, desafio, op_id):
    st.session_state.llamadas_gemini += 1
    return Resultado.exito(
        VerificacionFindIt(
            estado=EstadoFindIt.INDETERMINABLE,
            mensaje="Imagen con poca luz.",
        )
    )

renderizar_pantalla_find_it(cfg, verificar_fn=_verificar_contado, repositorio=repo)
"""
        at = AppTest.from_string(codigo)
        at.run()
        self.assertEqual(len(at.exception), 0)

        # Inyectar foto preparada y simular fallo de conexión a Supabase en el primer guardado
        img = Image.new("RGB", (320, 240), color=(100, 120, 140))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw = buf.getvalue()
        from homelens.imagenes import preparar_imagen

        prep = preparar_imagen(raw, max_bytes=5_000_000, max_dimension_px=1280).valor
        at.session_state["find_it_imagen_bytes"] = raw
        at.session_state["find_it_imagen_preparada"] = prep
        at.session_state["mock_client"].fallar_conexion = True
        at.run()

        btn_verif = next(b for b in at.button if b.key == "btn_verificar_find_it")
        btn_verif.click().run()
        self.assertEqual(len(at.exception), 0)

        # Gemini fue llamado 1 vez; el resultado INDETERMINABLE sigue visible pero el guardado falló
        self.assertEqual(at.session_state["llamadas_gemini"], 1)
        self.assertIsNotNone(at.session_state["find_it_verificacion"])
        self.assertEqual(
            at.session_state["find_it_verificacion"].estado,
            EstadoFindIt.INDETERMINABLE,
        )
        intento_generado = at.session_state["find_it_ultimo_intento"]
        self.assertIsNotNone(intento_generado)
        self.assertEqual(intento_generado.resultado, ResultadoIntento.INDETERMINABLE)
        self.assertFalse(at.session_state["find_it_intento_guardado"])
        self.assertIsNotNone(at.session_state["find_it_error_guardado"])

        # Reintentar guardado cuando vuelve la conexión: NO debe llamar otra vez a Gemini y conserva el mismo ID
        at.session_state["mock_client"].fallar_conexion = False
        btn_reintentar_guardado = next(
            b for b in at.button if b.key == "btn_reintentar_guardado_find_it"
        )
        btn_reintentar_guardado.click().run()
        self.assertEqual(len(at.exception), 0)

        self.assertEqual(at.session_state["llamadas_gemini"], 1)
        self.assertTrue(at.session_state["find_it_intento_guardado"])
        self.assertIsNone(at.session_state["find_it_error_guardado"])
        self.assertEqual(
            at.session_state["find_it_ultimo_intento"].intento_id,
            intento_generado.intento_id,
        )

        filas_bd = at.session_state["mock_client"].db.get("intentos_practica", [])
        self.assertEqual(len(filas_bd), 1)
        self.assertEqual(filas_bd[0]["id"], str(intento_generado.intento_id))
        self.assertEqual(filas_bd[0]["resultado"], "INDETERMINABLE")

        # Si pulsa "Volver a intentar" y verifica de nuevo, es un intento nuevo con un ID nuevo
        btn_nuevo = next(b for b in at.button if b.key == "btn_reintentar_find_it")
        btn_nuevo.click().run()
        at.session_state["find_it_imagen_bytes"] = raw
        at.session_state["find_it_imagen_preparada"] = prep
        at.run()

        btn_verif_2 = next(b for b in at.button if b.key == "btn_verificar_find_it")
        btn_verif_2.click().run()
        self.assertEqual(at.session_state["llamadas_gemini"], 2)
        segundo_intento = at.session_state["find_it_ultimo_intento"]
        self.assertNotEqual(segundo_intento.intento_id, intento_generado.intento_id)
        self.assertEqual(len(at.session_state["mock_client"].db.get("intentos_practica", [])), 2)


class TestMigracionSQLIntentosPractica(unittest.TestCase):
    """Validación estática del script SQL de la Parte 10."""

    def test_migracion_sql_intentos_practica_estructura_y_rls(self) -> None:
        self.assertTrue(
            RUTA_MIGRACION_TAREA_10.exists(),
            f"No existe el archivo de migración {RUTA_MIGRACION_TAREA_10}",
        )
        sql = RUTA_MIGRACION_TAREA_10.read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS public.intentos_practica", sql)
        self.assertIn("id UUID PRIMARY KEY", sql)
        self.assertIn("user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE", sql)
        self.assertIn("CHECK (tipo IN ('CUESTIONARIO', 'FIND_IT'))", sql)
        self.assertIn("CHECK (resultado IN ('CORRECTO', 'INCORRECTO', 'INDETERMINABLE'))", sql)
        self.assertIn("ALTER TABLE public.intentos_practica ENABLE ROW LEVEL SECURITY;", sql)
        self.assertIn("GRANT SELECT, INSERT ON TABLE public.intentos_practica TO authenticated;", sql)
        self.assertNotIn("GRANT UPDATE ON TABLE public.intentos_practica", sql)
        self.assertNotIn("GRANT DELETE ON TABLE public.intentos_practica", sql)
        self.assertIn("USING ((SELECT auth.uid()) = user_id)", sql)
        self.assertIn("WITH CHECK ((SELECT auth.uid()) = user_id)", sql)


if __name__ == "__main__":
    unittest.main()
