"""Adaptador de autenticación externa (Supabase Auth / Google OAuth).

Encapsula la comunicación con Supabase Auth para flujos OAuth PKCE,
validación de tokens JWT en el servidor, gestión de sesiones y cierre seguro.
"""

from __future__ import annotations
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict
from uuid import UUID, uuid4

from homelens.errores import (
    Resultado,
    CODIGO_CONFIGURACION_INVALIDA,
    CODIGO_ACCESO_DENEGADO,
    CODIGO_SERVICIO_NO_DISPONIBLE,
    CODIGO_SESION_REQUERIDA,
)
from homelens.modelos import (
    ContextoUsuario,
    SolicitudAcceso,
    SesionUsuario,
    Confirmacion,
)


class AdaptadorAutenticacion:
    """Cliente para la integración con el proveedor de autenticación Supabase Auth."""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        anon_key: Optional[str] = None,
        cliente_supabase: Optional[Any] = None,
    ):
        """Inicializa el adaptador.

        Args:
            supabase_url: URL pública del proyecto Supabase.
            anon_key: Clave anónima pública (anon key) del proyecto.
            cliente_supabase: Cliente Supabase opcional inyectado (usado en pruebas y mocks).
        """
        self.supabase_url = (supabase_url or "").strip()
        self.anon_key = (anon_key or "").strip()
        self._cliente_inyectado = cliente_supabase
        self._cliente_instancia: Optional[Any] = None

        # Almacén en memoria del servidor para correlación de solicitudes OAuth (PKCE y CSRF)
        # Clave: state (token aleatorio seguro), Valor: dict con verifier, timestamp y redirect_to
        self._solicitudes_pendientes: Dict[str, Dict[str, Any]] = {}

        # Almacén en memoria del servidor de sesiones activas verificadas
        # Clave: access_token, Valor: SesionUsuario
        self._sesiones_activas: Dict[str, SesionUsuario] = {}

    def _obtener_cliente(self) -> Optional[Any]:
        """Obtiene o inicializa el cliente de Supabase asegurando que no se use la service role key."""
        if self._cliente_inyectado is not None:
            return self._cliente_inyectado

        if not self.supabase_url or not self.anon_key:
            return None

        if self._cliente_instancia is None:
            try:
                from supabase import create_client
                self._cliente_instancia = create_client(self.supabase_url, self.anon_key)
            except Exception:
                return None

        return self._cliente_instancia

    def _limpiar_solicitudes_expiradas(self, max_edad_minutos: int = 10) -> None:
        """Purga solicitudes OAuth pendientes antiguas para prevenir fugas de memoria."""
        ahora = datetime.now(timezone.utc)
        limite = ahora - timedelta(minutes=max_edad_minutos)
        expiradas = [
            st for st, data in self._solicitudes_pendientes.items()
            if data.get("creado_en", ahora) < limite
        ]
        for st in expiradas:
            self._solicitudes_pendientes.pop(st, None)

    def generar_solicitud_oauth(self, retorno_permitido: str) -> Resultado[SolicitudAcceso]:
        """Inicia el flujo OAuth PKCE con Google mediante Supabase Auth.

        Genera un parámetro state criptográficamente seguro para prevenir ataques CSRF
        y preserva en memoria del servidor el code_verifier de PKCE.

        Args:
            retorno_permitido: URL de retorno hacia la aplicación después de la autenticación.

        Returns:
            Resultado[SolicitudAcceso]: Parámetros de la solicitud con URL de autorización y state.
        """
        cliente = self._obtener_cliente()
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de autenticación no está disponible (faltan credenciales de Supabase en .env).",
            )

        self._limpiar_solicitudes_expiradas()

        # Generar identificador de estado seguro para mitigación estricta de CSRF
        state_token = secrets.token_urlsafe(32)

        try:
            res_oauth = cliente.auth.sign_in_with_oauth({
                "provider": "google",
                "options": {
                    "redirect_to": retorno_permitido,
                    "query_params": {
                        "state": state_token,
                    },
                },
            })

            # Recuperar el code_verifier generado internamente por Supabase Auth PKCE
            code_verifier = None
            storage = getattr(cliente.auth, "_storage", None)
            storage_key = getattr(cliente.auth, "_storage_key", "supabase.auth.token")
            if storage is not None and hasattr(storage, "get_item"):
                code_verifier = storage.get_item(f"{storage_key}-code-verifier")

            # Preservar en el servidor para el intercambio posterior
            self._solicitudes_pendientes[state_token] = {
                "code_verifier": code_verifier,
                "creado_en": datetime.now(timezone.utc),
                "redirect_to": retorno_permitido,
            }

            url_auth = getattr(res_oauth, "url", None) or (res_oauth.get("url") if isinstance(res_oauth, dict) else "")

            if not url_auth:
                return Resultado.fallo(
                    codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                    mensaje_usuario="El proveedor de autenticación no devolvió una URL de redirección válida.",
                )

            solicitud = SolicitudAcceso(
                url_autorizacion=str(url_auth),
                proveedor="google",
                state=state_token,
                code_verifier=code_verifier,
            )
            return Resultado.exito(solicitud)

        except Exception:
            return Resultado.fallo(
                codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                mensaje_usuario="No fue posible conectar con el servicio de autenticación de Supabase.",
            )

    def intercambiar_codigo(
        self,
        auth_code: str,
        state: str,
        redirect_to: Optional[str] = None,
    ) -> Resultado[SesionUsuario]:
        """Intercambia el código de autorización temporal por una sesión y tokens de Supabase.

        Aplica validación de state contra CSRF y descarta el verifier de un solo uso.

        Args:
            auth_code: Código devuelto por el proveedor tras la autorización.
            state: Token devuelto para correlación y validación CSRF.
            redirect_to: URL de retorno registrada originalmente.

        Returns:
            Resultado[SesionUsuario]: Sesión validada con ContextoUsuario e identidad estable.
        """
        cliente = self._obtener_cliente()
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de autenticación no está configurado.",
            )

        # 1. Validación estricta de state anti-CSRF (token de un solo uso)
        solicitud_guardada = self._solicitudes_pendientes.pop(state, None)
        if not solicitud_guardada:
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario="El estado de autorización es inválido, ya fue utilizado o ha expirado. Por favor, intenta ingresar nuevamente.",
            )

        # 2. Comprobar antigüedad máxima de la solicitud (10 minutos)
        creado_en = solicitud_guardada.get("creado_en", datetime.now(timezone.utc))
        if datetime.now(timezone.utc) - creado_en > timedelta(minutes=10):
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario="La solicitud de inicio de sesión ha expirado por tiempo. Intenta ingresar nuevamente.",
            )

        code_verifier = solicitud_guardada.get("code_verifier")
        uri_efectiva = redirect_to or solicitud_guardada.get("redirect_to")

        # 3. Intercambio seguro en Supabase Auth
        try:
            params = {
                "auth_code": auth_code,
                "code_verifier": code_verifier or "",
                "redirect_to": uri_efectiva or "",
            }
            auth_response = cliente.auth.exchange_code_for_session(params)

            if not auth_response or not getattr(auth_response, "user", None) or not getattr(auth_response, "session", None):
                return Resultado.fallo(
                    codigo=CODIGO_ACCESO_DENEGADO,
                    mensaje_usuario="No se pudo obtener una sesión válida a partir de la autorización de Google.",
                )

            user = auth_response.user
            session = auth_response.session

            # Validación de la identidad devuelta: debe ser un UUID válido
            try:
                user_uuid = UUID(str(user.id))
            except (ValueError, TypeError, AttributeError):
                return Resultado.fallo(
                    codigo=CODIGO_ACCESO_DENEGADO,
                    mensaje_usuario="El identificador de usuario devuelto por el proveedor no es un UUID válido.",
                )

            nombre = None
            metadata = getattr(user, "user_metadata", None)
            if isinstance(metadata, dict):
                nombre = metadata.get("full_name") or metadata.get("name")

            contexto = ContextoUsuario(
                user_id=user_uuid,
                sesion_id=str(session.access_token),
                email=getattr(user, "email", None),
                nombre=nombre,
                es_demo=False,
            )

            sesion_usuario = SesionUsuario(
                contexto=contexto,
                access_token=str(session.access_token),
                refresh_token=str(session.refresh_token) if getattr(session, "refresh_token", None) else None,
                expira_en_timestamp=getattr(session, "expires_at", None),
                iniciada_en=datetime.now(timezone.utc),
            )

            # Registrar sesión activa en memoria
            self._sesiones_activas[str(session.access_token)] = sesion_usuario
            return Resultado.exito(sesion_usuario)

        except Exception as e:
            # Nunca exponer tokens ni trazas internas en el mensaje al usuario
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario="Error al validar la autorización con Google y Supabase. Por favor, intenta ingresar nuevamente.",
            )

    def verificar_sesion(self, access_token: str) -> Resultado[ContextoUsuario]:
        """Comprueba que el token de sesión esté vigente y validado por Supabase Auth.

        Si la sesión expiró localmente, intenta refrescarla automáticamente.
        Valida criptográficamente el JWT contra el proveedor en el servidor.

        Args:
            access_token: Token de acceso a verificar.

        Returns:
            Resultado[ContextoUsuario]: Identidad verificada o error de sesión requerida.
        """
        cliente = self._obtener_cliente()
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de autenticación no está configurado.",
            )

        sesion_local = self._sesiones_activas.get(access_token)

        # Si conocemos la sesión y detectamos que expiró:
        if sesion_local and sesion_local.ha_expirado:
            if sesion_local.refresh_token:
                res_refresco = self.refrescar_sesion(sesion_local.refresh_token)
                if res_refresco.ok and res_refresco.valor:
                    return Resultado.exito(res_refresco.valor.contexto)

            # Si no se pudo refrescar:
            self._sesiones_activas.pop(access_token, None)
            return Resultado.fallo(
                codigo=CODIGO_SESION_REQUERIDA,
                mensaje_usuario="Tu sesión ha expirado por inactividad. Por favor, vuelve a ingresar con Google.",
            )

        # Validación en el servidor mediante llamada a get_user
        try:
            user_response = cliente.auth.get_user(jwt=access_token)
            if not user_response or not getattr(user_response, "user", None):
                self._sesiones_activas.pop(access_token, None)
                return Resultado.fallo(
                    codigo=CODIGO_SESION_REQUERIDA,
                    mensaje_usuario="Sesión rechazada o revocada por el proveedor. Ingresa nuevamente.",
                )

            user = user_response.user
            user_uuid = UUID(str(user.id))
            nombre = None
            metadata = getattr(user, "user_metadata", None)
            if isinstance(metadata, dict):
                nombre = metadata.get("full_name") or metadata.get("name")

            contexto = ContextoUsuario(
                user_id=user_uuid,
                sesion_id=access_token,
                email=getattr(user, "email", None),
                nombre=nombre,
                es_demo=False,
            )
            return Resultado.exito(contexto)

        except Exception:
            self._sesiones_activas.pop(access_token, None)
            return Resultado.fallo(
                codigo=CODIGO_SESION_REQUERIDA,
                mensaje_usuario="No se pudo comprobar la validez de la sesión o las credenciales expiraron.",
            )

    def refrescar_sesion(self, refresh_token: str) -> Resultado[SesionUsuario]:
        """Renueva los tokens de acceso mediante el refresh_token emitido por Supabase.

        Args:
            refresh_token: Token de actualización emitido por el proveedor.

        Returns:
            Resultado[SesionUsuario]: Nueva sesión con tokens renovados.
        """
        cliente = self._obtener_cliente()
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de autenticación no está configurado.",
            )

        try:
            auth_response = cliente.auth.refresh_session(refresh_token)
            if not auth_response or not getattr(auth_response, "user", None) or not getattr(auth_response, "session", None):
                return Resultado.fallo(
                    codigo=CODIGO_SESION_REQUERIDA,
                    mensaje_usuario="No fue posible renovar la sesión de usuario.",
                )

            user = auth_response.user
            session = auth_response.session
            user_uuid = UUID(str(user.id))

            nombre = None
            metadata = getattr(user, "user_metadata", None)
            if isinstance(metadata, dict):
                nombre = metadata.get("full_name") or metadata.get("name")

            contexto = ContextoUsuario(
                user_id=user_uuid,
                sesion_id=str(session.access_token),
                email=getattr(user, "email", None),
                nombre=nombre,
                es_demo=False,
            )

            sesion_usuario = SesionUsuario(
                contexto=contexto,
                access_token=str(session.access_token),
                refresh_token=str(session.refresh_token) if getattr(session, "refresh_token", None) else None,
                expira_en_timestamp=getattr(session, "expires_at", None),
                iniciada_en=datetime.now(timezone.utc),
            )

            self._sesiones_activas[str(session.access_token)] = sesion_usuario
            return Resultado.exito(sesion_usuario)

        except Exception:
            return Resultado.fallo(
                codigo=CODIGO_SESION_REQUERIDA,
                mensaje_usuario="Error al renovar la sesión con el proveedor.",
            )

    def cerrar_sesion(self, access_token: Optional[str] = None) -> Resultado[Confirmacion]:
        """Invalida la sesión activa en el proveedor y descarta las referencias locales.

        Args:
            access_token: Token de acceso de la sesión a cerrar.

        Returns:
            Resultado[Confirmacion]: Confirmación del cierre de sesión.
        """
        if access_token:
            self._sesiones_activas.pop(access_token, None)

        cliente = self._obtener_cliente()
        if cliente is not None:
            try:
                cliente.auth.sign_out()
            except Exception:
                pass

        return Resultado.exito(
            Confirmacion(
                operacion_id=uuid4(),
                mensaje="Sesión revocada en el proveedor y referencias locales eliminadas.",
            )
        )
