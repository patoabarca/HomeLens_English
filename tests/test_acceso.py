"""Suite de pruebas unitarias para el Módulo M1 (Acceso de usuarios).

Verifica exhaustivamente los 10 requisitos de autenticación, control de sesiones,
seguridad contra CSRF/manipulación, identidad estable y compatibilidad con los módulos existentes.
"""

from __future__ import annotations
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta

from homelens.acceso import (
    iniciar_acceso,
    completar_acceso,
    obtener_usuario_actual,
    iniciar_acceso_demo,
    cerrar_sesion,
    reiniciar_adaptador_global,
    ID_USUARIO_DEMO,
    ID_SESION_DEMO,
)
from homelens.config import Configuracion
from homelens.errores import (
    CODIGO_CONFIGURACION_INVALIDA,
    CODIGO_ACCESO_DENEGADO,
    CODIGO_SESION_REQUERIDA,
    CODIGO_SERVICIO_NO_DISPONIBLE,
)
from homelens.integraciones.autenticacion import AdaptadorAutenticacion
from homelens.modelos import (
    ContextoUsuario,
    RespuestaAcceso,
    SolicitudAcceso,
    SesionUsuario,
    ImagenPreparada,
)
from homelens.analisis import analizar_exploracion


class MockSupabaseAuthUser:
    """Usuario simulado devuelto por Supabase Auth."""
    def __init__(self, user_id: str, email: str = "usuario.prueba@gmail.com", full_name: str = "Usuario Prueba"):
        self.id = user_id
        self.email = email
        self.user_metadata = {"full_name": full_name}


class MockSupabaseAuthSession:
    """Sesión simulada devuelta por Supabase Auth."""
    def __init__(self, access_token: str = "token_jwt_valido_123", expires_in: int = 3600):
        self.access_token = access_token
        self.refresh_token = f"refresh_{access_token}"
        self.expires_at = int(datetime.now(timezone.utc).timestamp()) + expires_in


class MockSupabaseAuthResponse:
    """Respuesta simulada de exchange_code_for_session."""
    def __init__(self, user: MockSupabaseAuthUser, session: MockSupabaseAuthSession):
        self.user = user
        self.session = session


class MockSupabaseStorage:
    """Almacén simulado de tokens para PKCE."""
    def __init__(self):
        self._items = {}

    def get_item(self, key: str):
        return self._items.get(key)

    def set_item(self, key: str, value: str):
        self._items[key] = value

    def remove_item(self, key: str):
        self._items.pop(key, None)


class MockSupabaseClient:
    """Cliente simulado de Supabase para pruebas controladas de autenticación."""
    def __init__(self):
        self.auth = MagicMock()
        self.auth._storage = MockSupabaseStorage()
        self.auth._storage_key = "supabase.auth.token"

        # Mock de sign_in_with_oauth
        def mock_sign_in_with_oauth(params):
            provider = params.get("provider", "google")
            opts = params.get("options", {})
            q = opts.get("query_params", {})
            state = q.get("state", "dummy_state")
            redirect_to = opts.get("redirect_to", "http://localhost:8501")
            # Simular generación interna del code_verifier PKCE
            self.auth._storage.set_item(f"{self.auth._storage_key}-code-verifier", "mock_code_verifier_secret")
            res = MagicMock()
            res.url = f"https://mock.supabase.co/auth/v1/authorize?provider={provider}&state={state}&redirect_to={redirect_to}"
            res.provider = provider
            return res

        self.auth.sign_in_with_oauth.side_effect = mock_sign_in_with_oauth


class TestAccesoUsuarios(unittest.TestCase):
    """Pruebas unitarias completas para M1 (Acceso de usuarios)."""

    def setUp(self) -> None:
        reiniciar_adaptador_global()

        self.uuid_estable_1 = UUID("11111111-2222-3333-4444-555555555555")
        self.uuid_estable_2 = UUID("99999999-8888-7777-6666-555555555555")

        self.config_valida = Configuracion(
            app_env="development",
            debug=True,
            log_level="INFO",
            app_port=8501,
            gemini_api_key="mock_gemini_key",
            gemini_model="gemini-2.5-flash",
            gemini_timeout_seconds=60.0,
            gemini_max_retries=1,
            supabase_url="https://ejemplo.supabase.co",
            supabase_anon_key="anon_key_publica_segura",
            supabase_service_role_key=None,
            google_tts_language_code="en-US",
            google_tts_voice_name="en-US-Standard-C",
            max_image_size_bytes=10_000_000,
            audio_cache_ttl_seconds=3600,
            rate_limit_exploraciones_por_minuto=10,
            auth_redirect_url="http://localhost:8501",
            auth_requerida=True,
            permitir_demo_local=False,
        )

        self.mock_client = MockSupabaseClient()
        self.adaptador = AdaptadorAutenticacion(
            supabase_url="https://ejemplo.supabase.co",
            anon_key="anon_key_publica_segura",
            cliente_supabase=self.mock_client,
        )

    def tearirDown(self) -> None:
        reiniciar_adaptador_global()

    # =========================================================================
    # Requisito 1: Usuario sin sesión -> Acceso protegido bloqueado
    # =========================================================================
    def test_01_usuario_sin_sesion_acceso_protegido_bloqueado(self) -> None:
        """Comprueba que sin sesión activa se rechacen las operaciones protegidas."""
        # 1. obtener_usuario_actual sin sesion_id
        res_usr = obtener_usuario_actual(sesion_id=None, config=self.config_valida, adaptador=self.adaptador)
        self.assertFalse(res_usr.ok)
        self.assertIsNone(res_usr.valor)
        self.assertIsNotNone(res_usr.error)
        self.assertEqual(res_usr.error.codigo, CODIGO_SESION_REQUERIDA)

        # 2. String vacío o espacios
        res_vacio = obtener_usuario_actual(sesion_id="   ", config=self.config_valida, adaptador=self.adaptador)
        self.assertFalse(res_vacio.ok)
        self.assertEqual(res_vacio.error.codigo, CODIGO_SESION_REQUERIDA)

        # 3. Operación protegida de análisis rechaza usuario None
        imagen_dummy = ImagenPreparada(contenido=b"\xff\xd8\xff\xe0" + b"\x00" * 20, mime_type="image/jpeg", ancho=100, alto=100)
        res_analisis = analizar_exploracion(
            usuario=None,  # type: ignore
            imagen=imagen_dummy,
            operacion_id=uuid4(),
        )
        self.assertFalse(res_analisis.ok)
        self.assertEqual(res_analisis.error.codigo, CODIGO_SESION_REQUERIDA)

    # =========================================================================
    # Requisito 2: Usuario autenticado -> Acceso autorizado
    # =========================================================================
    def test_02_usuario_autenticado_acceso_autorizado(self) -> None:
        """Comprueba que una sesión válida permita autorizar el acceso y obtener identidad."""
        # Configurar respuesta exitosa de get_user en el cliente simulado
        user_mock = MockSupabaseAuthUser(str(self.uuid_estable_1), email="lucas@gmail.com", full_name="Lucas Raul")
        resp_mock = MagicMock()
        resp_mock.user = user_mock
        self.mock_client.auth.get_user.return_value = resp_mock

        res = obtener_usuario_actual(
            sesion_id="token_jwt_valido_lucas",
            config=self.config_valida,
            adaptador=self.adaptador,
        )

        self.assertTrue(res.ok)
        self.assertIsNotNone(res.valor)
        self.assertEqual(res.valor.user_id, self.uuid_estable_1)
        self.assertEqual(res.valor.email, "lucas@gmail.com")
        self.assertEqual(res.valor.nombre, "Lucas Raul")
        self.assertFalse(res.valor.es_demo)

    # =========================================================================
    # Requisito 3: Identidad estable al repetir la consulta o recargar
    # =========================================================================
    def test_03_identidad_estable_al_repetir_consulta(self) -> None:
        """Verifica que el identificador (user_id) no sea aleatorio y se mantenga idéntico."""
        user_mock = MockSupabaseAuthUser(str(self.uuid_estable_1), email="estudiante@gmail.com")
        resp_mock = MagicMock()
        resp_mock.user = user_mock
        self.mock_client.auth.get_user.return_value = resp_mock

        token = "token_sesion_persistente"

        # Primera consulta (login inicial)
        res1 = obtener_usuario_actual(sesion_id=token, config=self.config_valida, adaptador=self.adaptador)
        self.assertTrue(res1.ok)
        id_primera_vez = res1.valor.user_id

        # Segunda consulta (simulando re-render o recarga de página en Streamlit)
        res2 = obtener_usuario_actual(sesion_id=token, config=self.config_valida, adaptador=self.adaptador)
        self.assertTrue(res2.ok)
        id_segunda_vez = res2.valor.user_id

        # Tercera consulta posterior
        res3 = obtener_usuario_actual(sesion_id=token, config=self.config_valida, adaptador=self.adaptador)
        self.assertTrue(res3.ok)
        id_tercera_vez = res3.valor.user_id

        # La identidad devuelta debe coincidir con la de Supabase y ser estrictamente estable
        self.assertEqual(id_primera_vez, self.uuid_estable_1)
        self.assertEqual(id_primera_vez, id_segunda_vez)
        self.assertEqual(id_segunda_vez, id_tercera_vez)

    # =========================================================================
    # Requisito 4: Sesión inválida o vencida -> Acceso rechazado
    # =========================================================================
    def test_04_sesion_invalida_o_vencida_acceso_rechazado(self) -> None:
        """Verifica que tokens revocados o expirados en el proveedor provoquen rechazo amigable."""
        # 1. Simular rechazo en get_user (token inválido o revocado)
        self.mock_client.auth.get_user.side_effect = Exception("JWT expired or invalid")

        res_invalido = obtener_usuario_actual(
            sesion_id="token_revocado_o_manipulado",
            config=self.config_valida,
            adaptador=self.adaptador,
        )
        self.assertFalse(res_invalido.ok)
        self.assertEqual(res_invalido.error.codigo, CODIGO_SESION_REQUERIDA)
        self.assertIn("expir", res_invalido.error.mensaje_usuario.lower())

        # 2. Simular sesión local expirada que falla al refrescar
        sesion_expirada = SesionUsuario(
            contexto=ContextoUsuario(user_id=self.uuid_estable_1, sesion_id="token_viejo"),
            access_token="token_viejo",
            refresh_token="refresh_invalido",
            expira_en_timestamp=int(datetime.now(timezone.utc).timestamp()) - 100,  # Expirado en el pasado
        )
        self.adaptador._sesiones_activas["token_viejo"] = sesion_expirada
        self.mock_client.auth.refresh_session.side_effect = Exception("Refresh token revoked")

        res_expirada = obtener_usuario_actual(
            sesion_id="token_viejo",
            config=self.config_valida,
            adaptador=self.adaptador,
        )
        self.assertFalse(res_expirada.ok)
        self.assertEqual(res_expirada.error.codigo, CODIGO_SESION_REQUERIDA)

    # =========================================================================
    # Requisito 5: Cierre de sesión -> Credenciales y datos descartados
    # =========================================================================
    def test_05_cierre_de_sesion_elimina_credenciales(self) -> None:
        """Verifica que al cerrar sesión se revoque el token y no pueda reutilizarse."""
        token = "token_activo_para_cerrar"
        user_mock = MockSupabaseAuthUser(str(self.uuid_estable_1))
        self.adaptador._sesiones_activas[token] = SesionUsuario(
            contexto=ContextoUsuario(user_id=self.uuid_estable_1, sesion_id=token),
            access_token=token,
        )

        # Ejecutar cierre de sesión
        res_cierre = cerrar_sesion(sesion_id=token, config=self.config_valida, adaptador=self.adaptador)
        self.assertTrue(res_cierre.ok)
        self.assertIn("cerrada", res_cierre.valor.mensaje.lower())

        # Comprobar que sign_out del proveedor fue llamado
        self.mock_client.auth.sign_out.assert_called()

        # Comprobar que la sesión fue eliminada de las sesiones locales
        self.assertNotIn(token, self.adaptador._sesiones_activas)

    # =========================================================================
    # Requisito 6: Error del proveedor -> Mensaje comprensible sin acceso indebido
    # =========================================================================
    def test_06_error_del_proveedor_mensaje_comprensible(self) -> None:
        """Comprueba que errores de OAuth retornados por Google no otorguen acceso y muestren mensaje claro."""
        # 1. Error de cancelación o acceso denegado enviado por el proveedor
        resp_error = RespuestaAcceso(
            error="access_denied",
            error_description="El usuario canceló la autorización en Google.",
        )
        res = completar_acceso(respuesta_proveedor=resp_error, config=self.config_valida, adaptador=self.adaptador)
        self.assertFalse(res.ok)
        self.assertEqual(res.error.codigo, CODIGO_ACCESO_DENEGADO)
        self.assertIn("canceló", res.error.mensaje_usuario)

        # 2. Falla interna durante el intercambio exchange_code_for_session
        # Iniciar primero flujo legítimo para tener state válido
        solicitud_res = self.adaptador.generar_solicitud_oauth(retorno_permitido="http://localhost:8501")
        state_valido = solicitud_res.valor.state

        # Forzar error de red en exchange_code_for_session
        self.mock_client.auth.exchange_code_for_session.side_effect = Exception("Supabase Auth 500 Network error")

        resp_con_falla = RespuestaAcceso(code="auth_code_123", state=state_valido)
        res_falla = completar_acceso(respuesta_proveedor=resp_con_falla, config=self.config_valida, adaptador=self.adaptador)

        self.assertFalse(res_falla.ok)
        self.assertEqual(res_falla.error.codigo, CODIGO_ACCESO_DENEGADO)
        self.assertIn("Error al validar la autorización", res_falla.error.mensaje_usuario)
        # Asegurar que no se expuso la excepción técnica interna ni credenciales
        self.assertNotIn("500", res_falla.error.mensaje_usuario)

    # =========================================================================
    # Requisito 7: Ausencia de configuración -> Aplicación controlada, sin demo silencioso
    # =========================================================================
    def test_07_ausencia_de_configuracion_sin_autenticacion_ficticia(self) -> None:
        """Verifica que sin credenciales de Supabase no se inventen identidades ni demo silencioso."""
        config_sin_supabase = Configuracion(
            app_env="production",
            debug=False,
            log_level="INFO",
            app_port=8501,
            gemini_api_key=None,
            gemini_model="gemini-2.5-flash",
            gemini_timeout_seconds=60.0,
            gemini_max_retries=1,
            supabase_url=None,       # Ausente
            supabase_anon_key=None,  # Ausente
            supabase_service_role_key=None,
            google_tts_language_code="en-US",
            google_tts_voice_name="en-US-Standard-C",
            max_image_size_bytes=10_000_000,
            audio_cache_ttl_seconds=3600,
            rate_limit_exploraciones_por_minuto=10,
            auth_redirect_url="http://localhost:8501",
            auth_requerida=True,
            permitir_demo_local=False,
        )

        # 1. iniciar_acceso falla de forma limpia y descriptiva
        res_ini = iniciar_acceso(retorno_permitido="http://localhost:8501", config=config_sin_supabase)
        self.assertFalse(res_ini.ok)
        self.assertEqual(res_ini.error.codigo, CODIGO_CONFIGURACION_INVALIDA)

        # 2. obtener_usuario_actual rechaza sin crear usuario dummy
        res_usr = obtener_usuario_actual(sesion_id=None, config=config_sin_supabase)
        self.assertFalse(res_usr.ok)
        self.assertEqual(res_usr.error.codigo, CODIGO_SESION_REQUERIDA)

        # 3. Intento de usar demo en producción es expresamente rechazado
        res_demo = iniciar_acceso_demo(config=config_sin_supabase)
        self.assertFalse(res_demo.ok)
        self.assertEqual(res_demo.error.codigo, CODIGO_ACCESO_DENEGADO)

    # =========================================================================
    # Requisito 8: Cambio de usuario -> Sin reutilización de datos privados
    # =========================================================================
    def test_08_cambio_de_usuario_limpieza_estricta_de_datos(self) -> None:
        """Verifica que al cambiar de usuario no se mezclen datos privados ni exploraciones."""
        import streamlit as st
        from homelens.ui.estado import inicializar_estado_sesion, cerrar_sesion_usuario

        inicializar_estado_sesion()

        # Usuario 1 inicia sesión y realiza una captura
        usr_1 = ContextoUsuario(user_id=self.uuid_estable_1, sesion_id="token_usuario_1", email="usr1@gmail.com")
        st.session_state.usuario = usr_1
        st.session_state.imagen_cargada_bytes = b"foto_privada_usuario_1"
        st.session_state.objeto_seleccionado_id = uuid4()
        st.session_state.exploracion_actual = "exploracion_privada_1"

        # Usuario 1 cierra sesión
        cerrar_sesion_usuario(config=self.config_valida)

        # Comprobar que todos los datos temporales del Usuario 1 fueron borrados
        self.assertIsNone(st.session_state.usuario)
        self.assertIsNone(st.session_state.imagen_cargada_bytes)
        self.assertIsNone(st.session_state.imagen_preparada)
        self.assertIsNone(st.session_state.objeto_seleccionado_id)
        self.assertIsNone(st.session_state.exploracion_actual)

        # Usuario 2 inicia sesión
        usr_2 = ContextoUsuario(user_id=self.uuid_estable_2, sesion_id="token_usuario_2", email="usr2@gmail.com")
        st.session_state.usuario = usr_2

        # Comprobar aislamiento: Usuario 2 no ve nada del Usuario 1
        self.assertEqual(st.session_state.usuario.user_id, self.uuid_estable_2)
        self.assertIsNone(st.session_state.imagen_cargada_bytes)
        self.assertIsNone(st.session_state.exploracion_actual)

    # =========================================================================
    # Requisito 9: Usuario manipulado o ataque CSRF -> Operación rechazada
    # =========================================================================
    def test_09_usuario_manipulado_o_ataque_csrf_rechazado(self) -> None:
        """Verifica que parámetros manipulados o states desconocidos sean bloqueados."""
        # 1. Ataque CSRF: retorno con state inventado que nunca inició en el servidor
        resp_csrf = RespuestaAcceso(code="codigo_valido_robado", state="state_falso_del_atacante")
        res_csrf = completar_acceso(respuesta_proveedor=resp_csrf, config=self.config_valida, adaptador=self.adaptador)

        self.assertFalse(res_csrf.ok)
        self.assertEqual(res_csrf.error.codigo, CODIGO_ACCESO_DENEGADO)
        self.assertIn("inválido", res_csrf.error.mensaje_usuario.lower())

        # 2. Objeto usuario manipulado en llamada a operación protegida
        class ObjetoManipulado:
            user_id = "este_no_es_un_uuid"
            sesion_id = "token_falso"

        imagen_dummy = ImagenPreparada(contenido=b"\xff\xd8\xff\xe0" + b"\x00" * 20, mime_type="image/jpeg", ancho=100, alto=100)
        res_analisis = analizar_exploracion(
            usuario=ObjetoManipulado(),  # type: ignore
            imagen=imagen_dummy,
            operacion_id=uuid4(),
        )
        self.assertFalse(res_analisis.ok)
        self.assertEqual(res_analisis.error.codigo, CODIGO_SESION_REQUERIDA)

    # =========================================================================
    # Requisito 10: Flujo PKCE completo con exchange exitoso
    # =========================================================================
    def test_10_flujo_pkce_completo_intercambio_exitoso(self) -> None:
        """Verifica el flujo completo OAuth PKCE: inicio, captura de verifier y canje."""
        # 1. Iniciar acceso
        res_inicio = iniciar_acceso(retorno_permitido="http://localhost:8501", config=self.config_valida, adaptador=self.adaptador)
        self.assertTrue(res_inicio.ok)
        state = res_inicio.valor.state
        self.assertIsNotNone(res_inicio.valor.code_verifier)
        self.assertIn("google", res_inicio.valor.url_autorizacion)

        # 2. Simular retorno exitoso de Supabase con código
        user_mock = MockSupabaseAuthUser(str(self.uuid_estable_1), email="estudiante.exitoso@gmail.com", full_name="Estudiante Exitoso")
        session_mock = MockSupabaseAuthSession("token_jwt_super_seguro", expires_in=3600)
        self.mock_client.auth.exchange_code_for_session.return_value = MockSupabaseAuthResponse(user_mock, session_mock)

        resp_oauth = RespuestaAcceso(code="auth_code_legitimo", state=state)
        res_comp = completar_acceso(respuesta_proveedor=resp_oauth, config=self.config_valida, adaptador=self.adaptador)

        self.assertTrue(res_comp.ok)
        self.assertEqual(res_comp.valor.user_id, self.uuid_estable_1)
        self.assertEqual(res_comp.valor.email, "estudiante.exitoso@gmail.com")
        self.assertEqual(res_comp.valor.nombre, "Estudiante Exitoso")
        self.assertEqual(res_comp.valor.sesion_id, "token_jwt_super_seguro")

        # 3. Comprobar que el state fue consumido y no puede usarse una segunda vez (replay attack)
        res_replay = completar_acceso(respuesta_proveedor=resp_oauth, config=self.config_valida, adaptador=self.adaptador)
        self.assertFalse(res_replay.ok)
        self.assertEqual(res_replay.error.codigo, CODIGO_ACCESO_DENEGADO)


if __name__ == "__main__":
    unittest.main()
