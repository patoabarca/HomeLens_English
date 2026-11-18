"""Pruebas unitarias e integración para el Panel de Consumo de IA (Gemini)."""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from homelens.config import (
    Configuracion,
    cargar_configuracion,
    es_creador_autorizado,
    obtener_nombre_creador,
)
from homelens.modelos import (
    ContextoUsuario,
    RegistroConsumoIA,
    FiltroConsumoIA,
    EventoTecnico,
)
from homelens.errores import CODIGO_ACCESO_DENEGADO
from homelens.datos.supabase import RepositorioSupabase
from homelens.telemetria import registrar_evento
from homelens.ui.consumo import calcular_resumen_consumo
from pathlib import Path
from streamlit.testing.v1 import AppTest
from homelens.acceso import reiniciar_adaptador_global
from homelens.errores import Resultado

RUTA_APP = str(Path(__file__).resolve().parent.parent / "app.py")

# UUIDs ficticios exclusivos para pruebas automatizadas (aislados del entorno real)
UUID_TEST_PATRICIA = UUID("11111111-1111-4111-8111-111111111111")
UUID_TEST_LUCAS = UUID("22222222-2222-4222-8222-222222222222")
UUID_TEST_VICTORIA = UUID("33333333-3333-4333-8333-333333333333")


class TestConsumoIA(unittest.TestCase):
    """Pruebas de acceso, repositorio, telemetría y KPIs de consumo."""

    def setUp(self) -> None:
        self.env_patcher = patch.dict(
            "os.environ",
            {
                "CREADOR_ID_PATRICIA": str(UUID_TEST_PATRICIA),
                "CREADOR_ID_LUCAS": str(UUID_TEST_LUCAS),
                "CREADOR_ID_VICTORIA": str(UUID_TEST_VICTORIA),
            },
        )
        self.env_patcher.start()

        self.config_res = cargar_configuracion()
        self.config = self.config_res.valor

        # Usuarios de prueba con identidades ficticias aisladas
        self.usuario_patricia = ContextoUsuario(
            user_id=UUID_TEST_PATRICIA,
            sesion_id="token_patricia",
            nombre="Patricia Abarca",
            es_demo=False,
        )
        self.usuario_lucas = ContextoUsuario(
            user_id=UUID_TEST_LUCAS,
            sesion_id="token_lucas",
            nombre="Lucas Centurión",
            es_demo=False,
        )
        self.usuario_victoria = ContextoUsuario(
            user_id=UUID_TEST_VICTORIA,
            sesion_id="token_victoria",
            nombre="Victoria Magliano",
            es_demo=False,
        )
        self.usuario_ajeno = ContextoUsuario(
            user_id=uuid4(),
            sesion_id="token_estudiante_ajeno",
            nombre="Estudiante Regular",
            es_demo=False,
        )
        self.usuario_demo = ContextoUsuario(
            user_id=UUID_TEST_PATRICIA,  # Mismo UUID pero en modo demo
            sesion_id="local_demo_session",
            nombre="Usuario Demo",
            es_demo=True,
        )

    def tearDown(self) -> None:
        self.env_patcher.stop()

    # =====================================================================
    # 1. Control de Acceso y Autorización
    # =====================================================================

    def test_creadores_autorizados_tienen_acceso(self) -> None:
        """Verifica que Patricia, Lucas y Victoria sean identificados como creadores."""
        self.assertTrue(es_creador_autorizado(self.usuario_patricia, self.config))
        self.assertTrue(es_creador_autorizado(self.usuario_lucas, self.config))
        self.assertTrue(es_creador_autorizado(self.usuario_victoria, self.config))

    def test_usuario_ajeno_queda_denegado(self) -> None:
        """Un usuario regular de Supabase no tiene acceso al panel de consumo."""
        self.assertFalse(es_creador_autorizado(self.usuario_ajeno, self.config))

    def test_modo_demo_queda_estrictamente_excluido(self) -> None:
        """El modo demo jamás tiene acceso al panel, incluso si tuviera el UUID de un creador."""
        self.assertFalse(es_creador_autorizado(self.usuario_demo, self.config))
        self.assertFalse(es_creador_autorizado(None, self.config))

    def test_obtener_nombre_creador(self) -> None:
        """Mapea UUIDs a los nombres amigables de presentación."""
        self.assertEqual(obtener_nombre_creador(UUID_TEST_PATRICIA, self.config), "Patricia")
        self.assertEqual(obtener_nombre_creador(UUID_TEST_LUCAS, self.config), "Lucas")
        self.assertEqual(obtener_nombre_creador(UUID_TEST_VICTORIA, self.config), "Victoria")
        self.assertEqual(obtener_nombre_creador(uuid4(), self.config), "Otro Integrante")

    def test_variable_faltante_deniega_acceso_por_defecto(self) -> None:
        """Si falta la variable de entorno de un creador, ese creador queda denegado por defecto."""
        with patch.dict("os.environ", {"CREADOR_ID_PATRICIA": str(UUID_TEST_PATRICIA), "CREADOR_ID_LUCAS": ""}, clear=True):
            res = cargar_configuracion()
            self.assertTrue(res.ok)
            cfg = res.valor
            self.assertTrue(es_creador_autorizado(self.usuario_patricia, cfg))
            self.assertFalse(es_creador_autorizado(self.usuario_lucas, cfg))
            self.assertFalse(es_creador_autorizado(self.usuario_victoria, cfg))

    def test_variable_invalida_deniega_acceso_por_defecto(self) -> None:
        """Si la variable de entorno contiene un formato que no es UUID, se deniega por defecto."""
        with patch.dict("os.environ", {"CREADOR_ID_PATRICIA": "no-es-un-uuid", "CREADOR_ID_LUCAS": str(UUID_TEST_LUCAS)}, clear=True):
            res = cargar_configuracion()
            self.assertTrue(res.ok)
            cfg = res.valor
            self.assertFalse(es_creador_autorizado(self.usuario_patricia, cfg))
            self.assertTrue(es_creador_autorizado(self.usuario_lucas, cfg))

    def test_sin_variables_creadores_deniega_a_todos(self) -> None:
        """Sin ninguna variable de creador en el entorno, nadie tiene acceso (default deny)."""
        with patch.dict(
            "os.environ",
            {
                "CREADOR_ID_PATRICIA": "",
                "CREADOR_ID_LUCAS": "",
                "CREADOR_ID_VICTORIA": "",
            },
        ):
            res = cargar_configuracion()
            self.assertTrue(res.ok)
            cfg = res.valor
            self.assertEqual(len(cfg.creadores_autorizados), 0)
            self.assertFalse(es_creador_autorizado(self.usuario_patricia, cfg))
            self.assertFalse(es_creador_autorizado(self.usuario_lucas, cfg))
            self.assertFalse(es_creador_autorizado(self.usuario_victoria, cfg))

    # =====================================================================
    # 2. Persistencia en RepositorioSupabase
    # =====================================================================

    def test_guardar_consumo_en_modo_demo_no_persiste(self) -> None:
        """El modo demo retorna éxito sin realizar llamadas de persistencia a Supabase."""
        mock_client = MagicMock()
        repo = RepositorioSupabase(cliente_supabase=mock_client)

        registro = RegistroConsumoIA(
            id=uuid4(),
            operacion_id=uuid4(),
            user_id=self.usuario_demo.user_id,
            fecha=datetime.now(timezone.utc),
            modelo="gemini-3.6-flash",
            estado="EXITO",
            duracion_ms=1200,
            numero_llamadas=1,
            numero_reintentos=0,
            costo_estimado=Decimal("0.002500"),
        )

        res = repo.registrar_consumo_gemini(self.usuario_demo, registro)
        self.assertTrue(res.ok)
        # No debe haber interactuado con PostgREST
        mock_client.table.assert_not_called()

    def test_guardar_consumo_denegado_para_usuario_no_creador(self) -> None:
        """Un usuario que no es creador autorizado no puede registrar consumos en Supabase."""
        mock_client = MagicMock()
        repo = RepositorioSupabase(cliente_supabase=mock_client)

        registro = RegistroConsumoIA(
            id=uuid4(),
            operacion_id=uuid4(),
            user_id=self.usuario_ajeno.user_id,
            fecha=datetime.now(timezone.utc),
            modelo="gemini-3.6-flash",
            estado="EXITO",
            duracion_ms=1000,
            numero_llamadas=1,
            numero_reintentos=0,
            costo_estimado=Decimal("0.002000"),
        )

        res = repo.registrar_consumo_gemini(self.usuario_ajeno, registro)
        self.assertFalse(res.ok)
        self.assertEqual(res.error.codigo, CODIGO_ACCESO_DENEGADO)
        mock_client.table.assert_not_called()

    def test_guardar_consumo_usuario_autenticado_invoca_upsert_idempotente(self) -> None:
        """Un usuario real registra el consumo con upsert sobre operacion_id."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])

        repo = RepositorioSupabase(cliente_supabase=mock_client)
        op_id = uuid4()
        registro = RegistroConsumoIA(
            id=uuid4(),
            operacion_id=op_id,
            user_id=self.usuario_patricia.user_id,
            fecha=datetime.now(timezone.utc),
            modelo="gemini-3.6-flash",
            estado="EXITO",
            duracion_ms=1500,
            numero_llamadas=1,
            numero_reintentos=0,
            prompt_tokens=800,
            candidates_tokens=400,
            total_tokens=1200,
            costo_estimado=Decimal("0.002100"),
        )

        res = repo.registrar_consumo_gemini(self.usuario_patricia, registro)
        self.assertTrue(res.ok)
        mock_client.table.assert_called_with("consumo_gemini")
        mock_table.upsert.assert_called_once()
        # Verificar idempotencia mediante on_conflict='operacion_id' e ignore_duplicates=True (ON CONFLICT DO NOTHING)
        self.assertEqual(mock_table.upsert.call_args[1].get("on_conflict"), "operacion_id")
        self.assertTrue(mock_table.upsert.call_args[1].get("ignore_duplicates"))

    def test_consultar_consumo_denegado_para_usuario_no_creador(self) -> None:
        """Rechaza la consulta de métricas si el usuario no es un creador verificado."""
        mock_client = MagicMock()
        repo = RepositorioSupabase(cliente_supabase=mock_client)

        res = repo.consultar_consumo_gemini(self.usuario_ajeno)
        self.assertFalse(res.ok)
        self.assertEqual(res.error.codigo, CODIGO_ACCESO_DENEGADO)
        mock_client.table.assert_not_called()

    def test_consultar_consumo_exitoso_para_creador(self) -> None:
        """Un creador puede consultar el listado de consumo con filtros."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order

        reg_id = uuid4()
        op_id = uuid4()
        mock_order.execute.return_value = MagicMock(
            data=[
                {
                    "id": str(reg_id),
                    "operacion_id": str(op_id),
                    "user_id": str(UUID_TEST_PATRICIA),
                    "fecha": "2026-11-17T12:00:00+00:00",
                    "modelo": "gemini-3.6-flash",
                    "estado": "EXITO",
                    "duracion_ms": 1100,
                    "numero_llamadas": 1,
                    "numero_reintentos": 0,
                    "codigo_error": None,
                    "prompt_tokens": 500,
                    "candidates_tokens": 200,
                    "thoughts_tokens": None,
                    "total_tokens": 700,
                    "cached_tokens": None,
                    "tarifa_version": "gemini-3.6-flash-2026-v1",
                    "costo_estimado": "0.001125",
                    "metadatos": {},
                }
            ]
        )

        repo = RepositorioSupabase(cliente_supabase=mock_client)
        res = repo.consultar_consumo_gemini(self.usuario_patricia)

        self.assertTrue(res.ok)
        self.assertEqual(len(res.valor), 1)
        r = res.valor[0]
        self.assertEqual(r.integrante_etiqueta, "Patricia")
        self.assertEqual(r.costo_estimado, Decimal("0.001125"))
        self.assertEqual(r.total_tokens, 700)

    # =====================================================================
    # 3. Telemetría Tolerante a Fallos
    # =====================================================================

    def test_telemetria_no_falla_si_repositorio_lanza_excepcion(self) -> None:
        """Un fallo en la base de datos durante la telemetría nunca lanza excepción ni rompe el flujo."""
        mock_repo = MagicMock()
        mock_repo.registrar_consumo_gemini.side_effect = RuntimeError("Base de datos no disponible")

        evento = EventoTecnico(
            operacion_id=uuid4(),
            tipo_operacion="analisis_exploracion_gemini",
            fecha=datetime.now(timezone.utc),
            duracion_ms=1000,
            estado="EXITO",
            numero_llamadas=1,
            numero_reintentos=0,
            uso_reportado={"prompt_token_count": 500, "candidates_token_count": 200},
        )

        # Debe ejecutarse de forma silenciosa sin propagar la excepción
        try:
            registrar_evento(evento, repositorio=mock_repo, usuario=self.usuario_patricia)
        except Exception as e:
            self.fail(f"registrar_evento lanzó excepción no deseada: {e}")

    # =====================================================================
    # 4. Cálculo de Métricas y KPIs (calcular_resumen_consumo)
    # =====================================================================

    def test_calculo_resumen_kpis(self) -> None:
        """Verifica la agregación de fotos, llamadas, tokens, reintentos y costo promedio."""
        r1 = RegistroConsumoIA(
            id=uuid4(),
            operacion_id=uuid4(),
            user_id=UUID_TEST_PATRICIA,
            fecha=datetime.now(timezone.utc),
            modelo="gemini-3.6-flash",
            estado="EXITO",
            duracion_ms=1000,
            numero_llamadas=2,  # 1 llamada + 1 reintento
            numero_reintentos=1,
            prompt_tokens=1000,
            candidates_tokens=500,
            total_tokens=1500,
            costo_estimado=Decimal("0.002625"),
        )
        r2 = RegistroConsumoIA(
            id=uuid4(),
            operacion_id=uuid4(),
            user_id=UUID_TEST_LUCAS,
            fecha=datetime.now(timezone.utc),
            modelo="gemini-3.6-flash",
            estado="ERROR",
            duracion_ms=800,
            numero_llamadas=1,
            numero_reintentos=0,
            prompt_tokens=None,
            candidates_tokens=None,
            total_tokens=None,
            costo_estimado=None,
        )

        resumen = calcular_resumen_consumo([r1, r2])

        self.assertEqual(resumen.total_fotografias, 1)  # Solo r1 fue EXITO
        self.assertEqual(resumen.total_solicitudes, 3)   # 2 + 1
        self.assertEqual(resumen.total_reintentos, 1)
        self.assertEqual(resumen.total_solicitudes_fallidas, 1)
        self.assertEqual(resumen.total_tokens, 1500)
        self.assertEqual(resumen.costo_acumulado, Decimal("0.002625"))
        # Costo promedio por foto exitosa = 0.002625 / 1 = 0.002625
        self.assertEqual(resumen.costo_promedio_por_foto, Decimal("0.002625"))


# =====================================================================
# 5. Pruebas de Interfaz (Streamlit AppTest)
# =====================================================================

class TestUIConsumoIA(unittest.TestCase):
    """Pruebas de interfaz interactiva con AppTest para la sección Consumo de IA."""

    def setUp(self) -> None:
        reiniciar_adaptador_global()
        self.env_patcher = patch.dict(
            "os.environ",
            {
                "CREADOR_ID_PATRICIA": str(UUID_TEST_PATRICIA),
                "CREADOR_ID_LUCAS": str(UUID_TEST_LUCAS),
                "CREADOR_ID_VICTORIA": str(UUID_TEST_VICTORIA),
            },
        )
        self.env_patcher.start()

        self.usuario_patricia = ContextoUsuario(
            user_id=UUID_TEST_PATRICIA,
            sesion_id="token_patricia",
            nombre="Patricia Abarca",
            es_demo=False,
        )
        self.usuario_ajeno = ContextoUsuario(
            user_id=uuid4(),
            sesion_id="token_ajeno",
            nombre="Estudiante Regular",
            es_demo=False,
        )
        self.usuario_demo = ContextoUsuario(
            user_id=UUID_TEST_PATRICIA,
            sesion_id="local_demo_session",
            nombre="Usuario Demo",
            es_demo=True,
        )

    def tearDown(self) -> None:
        self.env_patcher.stop()
        reiniciar_adaptador_global()

    def test_creador_ve_opcion_consumo_en_menu(self) -> None:
        """Un creador autenticado ve 'Consumo de IA' en las opciones de navegación."""
        with patch("homelens.acceso.obtener_usuario_actual", return_value=Resultado.exito(self.usuario_patricia)):
            at = AppTest.from_file(RUTA_APP, default_timeout=15)
            at.session_state.usuario = self.usuario_patricia
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertIn("Consumo de IA", at.radio[0].options)

    def test_usuario_regular_no_ve_opcion_consumo(self) -> None:
        """Un estudiante regular autenticado NO ve la opción 'Consumo de IA' en el menú."""
        with patch("homelens.acceso.obtener_usuario_actual", return_value=Resultado.exito(self.usuario_ajeno)):
            at = AppTest.from_file(RUTA_APP, default_timeout=15)
            at.session_state.usuario = self.usuario_ajeno
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertNotIn("Consumo de IA", at.radio[0].options)

    def test_modo_demo_no_ve_opcion_consumo(self) -> None:
        """El modo demo local NO ve la opción 'Consumo de IA' en el menú."""
        at = AppTest.from_file(RUTA_APP, default_timeout=15)
        at.session_state.usuario = self.usuario_demo
        at.run()
        self.assertEqual(len(at.exception), 0)
        self.assertNotIn("Consumo de IA", at.radio[0].options)

    def test_renderizar_panel_consumo_con_preview_simulado(self) -> None:
        """Verifica que el panel se renderice con datos simulados sin excepciones."""
        with patch("homelens.acceso.obtener_usuario_actual", return_value=Resultado.exito(self.usuario_patricia)):
            at = AppTest.from_file(RUTA_APP, default_timeout=15)
            at.session_state.usuario = self.usuario_patricia
            at.session_state.seccion_navegacion = "Consumo de IA"
            at.session_state._preview_consumo_ficticio = True
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertGreater(len(at.metric), 0)


# =====================================================================
# 6. Verificación de Formatos, Indicadores y Consistencia Matemática
# =====================================================================

class TestConsumoDetalladoYFiltros(unittest.TestCase):
    """Pruebas rigurosas de formatos, diferencias entre llamadas y operaciones, y datos simulados."""

    def setUp(self) -> None:
        self.config = Configuracion(
            app_env="testing",
            debug=True,
            log_level="INFO",
            app_port=8501,
            gemini_api_key="test_key",
            gemini_model="gemini-3.6-flash",
            gemini_timeout_seconds=30.0,
            gemini_max_retries=2,
            supabase_url="http://localhost:54321",
            supabase_anon_key="test_anon",
            supabase_service_role_key=None,
            google_tts_language_code="en-US",
            google_tts_voice_name="en-US-Neural2-F",
            max_image_size_bytes=10000000,
            audio_cache_ttl_seconds=86400,
            rate_limit_exploraciones_por_minuto=10,
            creadores_autorizados={
                UUID_TEST_PATRICIA: "Patricia",
                UUID_TEST_LUCAS: "Lucas",
                UUID_TEST_VICTORIA: "Victoria",
            },
        )

    def test_formato_fecha_hora_argentina(self) -> None:
        """Comprueba el formato 'DD/MM/YYYY · HH:MM ART' en hora local argentina."""
        from homelens.ui.consumo import formatear_fecha_argentina
        # 17 de noviembre de 2026, 23:58:00 UTC = 20:58:00 ART
        dt_utc = datetime(2026, 11, 17, 23, 58, 0, tzinfo=timezone.utc)
        resultado = formatear_fecha_argentina(dt_utc)
        self.assertEqual(resultado, "17/11/2026 · 20:58 ART")

    def test_coherencia_matematica_datos_simulados(self) -> None:
        """Verifica la consistencia matemática exacta del lote sintético de 12 operaciones."""
        from homelens.ui.consumo import generar_datos_simulados_consumo

        simulados = generar_datos_simulados_consumo(self.config)
        self.assertEqual(len(simulados), 12)

        # Integrantes representados
        integrantes = {r.integrante_etiqueta for r in simulados}
        self.assertEqual(integrantes, {"Patricia", "Lucas", "Victoria"})

        # Verificación de operaciones y llamadas
        resumen = calcular_resumen_consumo(simulados)
        self.assertEqual(resumen.total_fotografias, 10)  # 10 exitosas
        self.assertEqual(resumen.total_solicitudes_fallidas, 2)  # 2 con error
        self.assertEqual(resumen.total_solicitudes, 14)  # 10 + 2 + 2 = 14 llamadas HTTP
        self.assertEqual(resumen.total_reintentos, 2)    # 2 reintentos registrados
        self.assertEqual(resumen.total_tokens, 17390)   # Suma exacta de tokens
        self.assertEqual(resumen.costo_acumulado, Decimal("0.027633"))
        self.assertEqual(resumen.costo_promedio_por_foto, Decimal("0.002763"))

        # Distinción estricta: llamadas > operaciones
        self.assertGreater(resumen.total_solicitudes, len(simulados))

    def test_conciliacion_economica_individual_vs_total(self) -> None:
        """Auditoría económica: concilia cada costo individual, suma acumulada y desglose por integrante y día."""
        from homelens.ui.consumo import generar_datos_simulados_consumo

        simulados = generar_datos_simulados_consumo(self.config)
        resumen = calcular_resumen_consumo(simulados)

        # 1. Suma manual directa de los costos individuales conocidos
        costos_individuales = [r.costo_estimado for r in simulados if r.costo_estimado is not None]
        self.assertEqual(len(costos_individuales), 10)
        suma_manual = sum(costos_individuales, Decimal("0.000000"))
        self.assertEqual(suma_manual, Decimal("0.027633"))
        self.assertEqual(resumen.costo_acumulado, suma_manual)

        # 2. Promedio por fotografía exitosa con costo conocido
        self.assertEqual(resumen.costo_promedio_por_foto, Decimal("0.002763"))

        # 3. Conciliación por integrante (debe sumar exactamente el total acumulado)
        costo_por_integrante = {
            "Patricia": sum((r.costo_estimado for r in simulados if r.integrante_etiqueta == "Patricia" and r.costo_estimado is not None), Decimal("0")),
            "Lucas": sum((r.costo_estimado for r in simulados if r.integrante_etiqueta == "Lucas" and r.costo_estimado is not None), Decimal("0")),
            "Victoria": sum((r.costo_estimado for r in simulados if r.integrante_etiqueta == "Victoria" and r.costo_estimado is not None), Decimal("0")),
        }
        suma_integrantes = sum(costo_por_integrante.values(), Decimal("0"))
        self.assertEqual(suma_integrantes, Decimal("0.027633"))
        self.assertEqual(costo_por_integrante["Patricia"], Decimal("0.008858"))
        self.assertEqual(costo_por_integrante["Lucas"], Decimal("0.008544"))
        self.assertEqual(costo_por_integrante["Victoria"], Decimal("0.010231"))

        # 4. Verificación de fórmulas individuales según tarifas 2026 de gemini-3.6-flash:
        # Se verifica contra el motor oficial calcular_costo_gemini con Decimal exacto
        from homelens.costos import calcular_costo_gemini
        for r in simulados:
            if r.costo_estimado is not None:
                calc = calcular_costo_gemini(
                    modelo=r.modelo,
                    prompt_tokens=r.prompt_tokens,
                    candidates_tokens=r.candidates_tokens,
                    thoughts_tokens=r.thoughts_tokens,
                    cached_tokens=r.cached_tokens,
                    fecha=r.fecha,
                )
                self.assertEqual(r.costo_estimado, calc.costo_estimado)

    def test_distincion_operaciones_vs_llamadas_http(self) -> None:
        """Cuatro operaciones pueden ser 3 éxitos, 1 fallo y 6 llamadas si hay 2 reintentos."""
        op1 = RegistroConsumoIA(
            id=uuid4(), operacion_id=uuid4(), user_id=UUID_TEST_PATRICIA,
            fecha=datetime.now(timezone.utc), modelo="gemini-3.6-flash",
            estado="EXITO", duracion_ms=1000, numero_llamadas=1, numero_reintentos=0,
            costo_estimado=Decimal("0.001000"),
        )
        op2 = RegistroConsumoIA(
            id=uuid4(), operacion_id=uuid4(), user_id=UUID_TEST_PATRICIA,
            fecha=datetime.now(timezone.utc), modelo="gemini-3.6-flash",
            estado="EXITO", duracion_ms=1500, numero_llamadas=2, numero_reintentos=1,
            costo_estimado=Decimal("0.001500"),
        )
        op3 = RegistroConsumoIA(
            id=uuid4(), operacion_id=uuid4(), user_id=UUID_TEST_LUCAS,
            fecha=datetime.now(timezone.utc), modelo="gemini-3.6-flash",
            estado="EXITO", duracion_ms=1000, numero_llamadas=1, numero_reintentos=0,
            costo_estimado=Decimal("0.001000"),
        )
        op4 = RegistroConsumoIA(
            id=uuid4(), operacion_id=uuid4(), user_id=UUID_TEST_VICTORIA,
            fecha=datetime.now(timezone.utc), modelo="gemini-3.6-flash",
            estado="ERROR", duracion_ms=1200, numero_llamadas=2, numero_reintentos=1,
            costo_estimado=None,
        )

        resumen = calcular_resumen_consumo([op1, op2, op3, op4])
        self.assertEqual(resumen.total_fotografias, 3)          # 3 fotos exitosas
        self.assertEqual(resumen.total_solicitudes_fallidas, 1) # 1 op fallida
        self.assertEqual(resumen.total_solicitudes, 6)          # 1 + 2 + 1 + 2 = 6 llamadas API
        self.assertEqual(resumen.total_reintentos, 2)           # 2 reintentos
        self.assertEqual(resumen.costo_acumulado, Decimal("0.003500"))
        # Costo promedio: 0.003500 / 3 fotos = 0.001167
        self.assertEqual(resumen.costo_promedio_por_foto, Decimal("0.001167"))

    def test_costo_promedio_con_costo_desconocido(self) -> None:
        """No divide costos desconocidos por cero ni asigna cero artificialmente."""
        op_sin_costo = RegistroConsumoIA(
            id=uuid4(), operacion_id=uuid4(), user_id=UUID_TEST_PATRICIA,
            fecha=datetime.now(timezone.utc), modelo="gemini-3.6-flash",
            estado="ERROR", duracion_ms=500, numero_llamadas=1, numero_reintentos=0,
            costo_estimado=None,
        )
        resumen = calcular_resumen_consumo([op_sin_costo])
        self.assertEqual(resumen.total_fotografias, 0)
        self.assertEqual(resumen.costo_acumulado, Decimal("0"))
        self.assertIsNone(resumen.costo_promedio_por_foto)


class TestCompatibilidadContratoPythonSQL(unittest.TestCase):
    """Auditoría y verificación del contrato entre modelos Python y el esquema SQL de Supabase."""

    def setUp(self) -> None:
        self.ruta_sql = Path(__file__).resolve().parent.parent / "sql" / "migracion_tarea_consumo_ia.sql"
        self.assertTrue(self.ruta_sql.exists(), "Falta el archivo sql/migracion_tarea_consumo_ia.sql")
        self.sql_texto = self.ruta_sql.read_text(encoding="utf-8")

        self.usuario_patricia = ContextoUsuario(
            user_id=UUID_TEST_PATRICIA,
            sesion_id="token_patricia",
            nombre="Patricia Abarca",
            es_demo=False,
        )
        self.env_patcher = patch.dict(
            "os.environ",
            {
                "CREADOR_ID_PATRICIA": str(UUID_TEST_PATRICIA),
                "CREADOR_ID_LUCAS": str(UUID_TEST_LUCAS),
                "CREADOR_ID_VICTORIA": str(UUID_TEST_VICTORIA),
            },
        )
        self.env_patcher.start()

    def tearDown(self) -> None:
        self.env_patcher.stop()

    def _extraer_columnas_tabla_sql(self, nombre_tabla: str) -> set[str]:
        """Extrae el conjunto de nombres de columnas definidos en el CREATE TABLE del script SQL."""
        import re
        patron = re.compile(
            rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+public\.{nombre_tabla}\s*\((.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )
        match = patron.search(self.sql_texto)
        self.assertIsNotNone(match, f"No se encontró CREATE TABLE para public.{nombre_tabla} en SQL")

        cuerpo = match.group(1)
        columnas = set()
        for linea in cuerpo.splitlines():
            linea_limpia = linea.strip().rstrip(",")
            if not linea_limpia:
                continue
            if linea_limpia.upper().startswith("CONSTRAINT"):
                break  # Las columnas terminan al comenzar las restricciones
            partes = linea_limpia.split()
            if partes:
                col_nombre = partes[0].lower()
                columnas.add(col_nombre)
        return columnas

    def test_columnas_serializadas_coinciden_exactamente_con_esquema_sql(self) -> None:
        """Verifica que cada columna serializada por Python en fila exista en consumo_gemini y viceversa."""
        columnas_sql = self._extraer_columnas_tabla_sql("consumo_gemini")

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = MagicMock(data=[])

        repo = RepositorioSupabase(cliente_supabase=mock_client)

        registro = RegistroConsumoIA(
            id=uuid4(),
            operacion_id=uuid4(),
            user_id=self.usuario_patricia.user_id,
            fecha=datetime.now(timezone.utc),
            modelo="gemini-3.6-flash",
            estado="EXITO",
            duracion_ms=1200,
            numero_llamadas=1,
            numero_reintentos=0,
            codigo_error=None,
            prompt_tokens=1000,
            candidates_tokens=300,
            thoughts_tokens=50,
            total_tokens=1350,
            cached_tokens=200,
            tarifa_version="gemini-3.6-flash-2026-v2",
            costo_estimado=Decimal("0.001875"),
            metadatos={"modulo": "analisis"},
        )

        res = repo.registrar_consumo_gemini(self.usuario_patricia, registro)
        self.assertTrue(res.ok)

        # Extraer el argumento 'fila' pasado a upsert
        call_args = mock_table.upsert.call_args
        fila_enviada = call_args[0][0]
        columnas_python = set(fila_enviada.keys())

        # Comparación estricta de conjuntos
        self.assertEqual(
            columnas_python,
            columnas_sql,
            f"Discrepancia entre columnas serializadas por Python y columnas SQL.\n"
            f"En Python pero no en SQL: {columnas_python - columnas_sql}\n"
            f"En SQL pero no en Python: {columnas_sql - columnas_python}",
        )

    def test_serializacion_y_deserializacion_roundtrip_con_cache_y_costo(self) -> None:
        """Comprueba que una operación con cached_tokens y costo estimado reconstruya el modelo fielmente."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = MagicMock(data=[])
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order

        repo = RepositorioSupabase(cliente_supabase=mock_client)

        reg_id = uuid4()
        op_id = uuid4()
        fecha_ahora = datetime(2026, 11, 18, 14, 0, 0, tzinfo=timezone.utc)

        registro_original = RegistroConsumoIA(
            id=reg_id,
            operacion_id=op_id,
            user_id=self.usuario_patricia.user_id,
            fecha=fecha_ahora,
            modelo="gemini-3.6-flash",
            estado="EXITO",
            duracion_ms=1350,
            numero_llamadas=1,
            numero_reintentos=0,
            codigo_error=None,
            prompt_tokens=1200,
            candidates_tokens=250,
            thoughts_tokens=50,
            total_tokens=1500,
            cached_tokens=400,
            tarifa_version="gemini-3.6-flash-2026-v2",
            costo_estimado=Decimal("0.001755"),
            metadatos={"cache_hit": True},
        )

        # 1. Escritura (Serialización)
        res_write = repo.registrar_consumo_gemini(self.usuario_patricia, registro_original)
        self.assertTrue(res_write.ok)

        # Comprobar llamada idempotente a PostgREST con ignore_duplicates
        upsert_kwargs = mock_table.upsert.call_args[1]
        self.assertEqual(upsert_kwargs.get("on_conflict"), "operacion_id")
        self.assertTrue(upsert_kwargs.get("ignore_duplicates"))

        fila_serializada = mock_table.upsert.call_args[0][0]
        self.assertEqual(fila_serializada["cached_tokens"], 400)
        self.assertEqual(fila_serializada["costo_estimado"], "0.001755")
        self.assertEqual(fila_serializada["estado"], "EXITO")
        self.assertEqual(fila_serializada["tarifa_version"], "gemini-3.6-flash-2026-v2")

        # 2. Lectura (Deserialización simulando respuesta de PostgREST)
        mock_order.execute.return_value = MagicMock(data=[fila_serializada])

        res_read = repo.consultar_consumo_gemini(self.usuario_patricia)
        self.assertTrue(res_read.ok)
        self.assertEqual(len(res_read.valor), 1)

        reg_recuperado = res_read.valor[0]
        self.assertEqual(reg_recuperado.id, reg_id)
        self.assertEqual(reg_recuperado.operacion_id, op_id)
        self.assertEqual(reg_recuperado.user_id, self.usuario_patricia.user_id)
        self.assertEqual(reg_recuperado.fecha, fecha_ahora)
        self.assertEqual(reg_recuperado.modelo, "gemini-3.6-flash")
        self.assertEqual(reg_recuperado.estado, "EXITO")
        self.assertEqual(reg_recuperado.duracion_ms, 1350)
        self.assertEqual(reg_recuperado.numero_llamadas, 1)
        self.assertEqual(reg_recuperado.numero_reintentos, 0)
        self.assertIsNone(reg_recuperado.codigo_error)
        self.assertEqual(reg_recuperado.prompt_tokens, 1200)
        self.assertEqual(reg_recuperado.candidates_tokens, 250)
        self.assertEqual(reg_recuperado.thoughts_tokens, 50)
        self.assertEqual(reg_recuperado.total_tokens, 1500)
        self.assertEqual(reg_recuperado.cached_tokens, 400)
        self.assertEqual(reg_recuperado.tarifa_version, "gemini-3.6-flash-2026-v2")
        self.assertEqual(reg_recuperado.costo_estimado, Decimal("0.001755"))
        self.assertEqual(reg_recuperado.integrante_etiqueta, "Patricia")
        self.assertEqual(reg_recuperado.metadatos, {"cache_hit": True})

    def test_operacion_fallida_con_costos_y_tokens_desconocidos_persiste_null(self) -> None:
        """Una operación fallida (HTTP 429) serializa y deserializa con NULL sin sustituir por cero."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = MagicMock(data=[])
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order

        repo = RepositorioSupabase(cliente_supabase=mock_client)

        reg_id = uuid4()
        op_id = uuid4()
        fecha_error = datetime(2026, 11, 18, 14, 30, 0, tzinfo=timezone.utc)

        registro_fallido = RegistroConsumoIA(
            id=reg_id,
            operacion_id=op_id,
            user_id=self.usuario_patricia.user_id,
            fecha=fecha_error,
            modelo="gemini-3.6-flash",
            estado="ERROR",
            duracion_ms=450,
            numero_llamadas=1,
            numero_reintentos=0,
            codigo_error=429,
            prompt_tokens=None,
            candidates_tokens=None,
            thoughts_tokens=None,
            total_tokens=None,
            cached_tokens=None,
            tarifa_version="gemini-3.6-flash-2026-v2",
            costo_estimado=None,
            metadatos={"error": "RESOURCE_EXHAUSTED", "http_code": 429},
        )

        # 1. Escritura
        res_write = repo.registrar_consumo_gemini(self.usuario_patricia, registro_fallido)
        self.assertTrue(res_write.ok)

        fila = mock_table.upsert.call_args[0][0]

        # Comprobar rigurosamente que los datos desconocidos son None (SQL NULL), NUNCA cero
        self.assertIsNone(fila["costo_estimado"])
        self.assertIsNone(fila["prompt_tokens"])
        self.assertIsNone(fila["candidates_tokens"])
        self.assertIsNone(fila["thoughts_tokens"])
        self.assertIsNone(fila["total_tokens"])
        self.assertIsNone(fila["cached_tokens"])
        self.assertEqual(fila["codigo_error"], 429)
        self.assertEqual(fila["estado"], "ERROR")

        # 2. Lectura y reconstrucción
        mock_order.execute.return_value = MagicMock(data=[fila])

        res_read = repo.consultar_consumo_gemini(self.usuario_patricia)
        self.assertTrue(res_read.ok)
        rec = res_read.valor[0]

        self.assertEqual(rec.estado, "ERROR")
        self.assertEqual(rec.codigo_error, 429)
        self.assertIsNone(rec.costo_estimado)
        self.assertIsNone(rec.prompt_tokens)
        self.assertIsNone(rec.candidates_tokens)
        self.assertIsNone(rec.thoughts_tokens)
        self.assertIsNone(rec.total_tokens)
        self.assertIsNone(rec.cached_tokens)
        self.assertEqual(rec.metadatos, {"error": "RESOURCE_EXHAUSTED", "http_code": 429})

    def test_restricciones_check_sql_admiten_operaciones_fallidas_y_cache(self) -> None:
        """Comprueba que el SQL admita explícitamente valores NULL para costos y tokens."""
        self.assertIn("chk_consumo_costo_no_negativo", self.sql_texto)
        self.assertIn("costo_estimado IS NULL OR costo_estimado >= 0", self.sql_texto)

        self.assertIn("chk_consumo_tokens_no_negativos", self.sql_texto)
        self.assertIn("prompt_tokens IS NULL OR prompt_tokens >= 0", self.sql_texto)
        self.assertIn("cached_tokens IS NULL OR cached_tokens >= 0", self.sql_texto)

        self.assertIn("chk_consumo_gemini_estado", self.sql_texto)
        self.assertIn("'ERROR'", self.sql_texto)
        self.assertIn("'EXITO'", self.sql_texto)


if __name__ == "__main__":
    unittest.main()
