"""Módulo M1: Acceso de usuarios, contexto de identidad y control de sesiones.

Implementa la gestión de autenticación mediante Google y Supabase Auth,
obteniendo una identidad estable por usuario y bloqueando operaciones protegidas
en ausencia de una sesión válida.
"""

from __future__ import annotations
from typing import Optional
from uuid import UUID, uuid4

from homelens.config import Configuracion, cargar_configuracion
from homelens.errores import (
    Resultado,
    CODIGO_CONFIGURACION_INVALIDA,
    CODIGO_ACCESO_DENEGADO,
    CODIGO_SESION_REQUERIDA,
)
from homelens.integraciones.autenticacion import AdaptadorAutenticacion
from homelens.modelos import (
    ContextoUsuario,
    SolicitudAcceso,
    RespuestaAcceso,
    Confirmacion,
)

# Identificador fijo del usuario de pruebas locales (modo demostración explícito)
ID_USUARIO_DEMO = UUID("00000000-0000-0000-0000-000000000001")
ID_SESION_DEMO = "local_demo_session"

# Adaptador singleton en memoria
_adaptador_global: Optional[AdaptadorAutenticacion] = None


def _obtener_adaptador(
    config: Optional[Configuracion] = None,
    adaptador: Optional[AdaptadorAutenticacion] = None,
) -> Optional[AdaptadorAutenticacion]:
    """Obtiene el adaptador inyectado o reutiliza la instancia configurada."""
    global _adaptador_global
    if adaptador is not None:
        return adaptador

    if _adaptador_global is not None:
        return _adaptador_global

    cfg = config
    if cfg is None:
        res_cfg = cargar_configuracion()
        if res_cfg.ok and res_cfg.valor:
            cfg = res_cfg.valor

    if cfg and cfg.tiene_supabase:
        _adaptador_global = AdaptadorAutenticacion(
            supabase_url=cfg.supabase_url,
            anon_key=cfg.supabase_anon_key,
        )
        return _adaptador_global

    return None


def reiniciar_adaptador_global() -> None:
    """Reinicia el adaptador global en memoria (usado en suites de pruebas)."""
    global _adaptador_global
    _adaptador_global = None


def iniciar_acceso(
    retorno_permitido: str,
    config: Optional[Configuracion] = None,
    adaptador: Optional[AdaptadorAutenticacion] = None,
) -> Resultado[SolicitudAcceso]:
    """Inicia el flujo de autenticación con Google mediante Supabase Auth.

    Args:
        retorno_permitido: URL a la que el navegador será redirigido tras autenticar.
        config: Configuración de la aplicación opcional.
        adaptador: Adaptador de autenticación inyectado opcional.

    Returns:
        Resultado[SolicitudAcceso]: Datos necesarios para redirigir al usuario al proveedor.
    """
    adapt = _obtener_adaptador(config=config, adaptador=adaptador)
    if adapt is None:
        return Resultado.fallo(
            codigo=CODIGO_CONFIGURACION_INVALIDA,
            mensaje_usuario="El servicio de autenticación con Google no está configurado (faltan credenciales de Supabase en .env).",
        )

    return adapt.generar_solicitud_oauth(retorno_permitido=retorno_permitido)


def completar_acceso(
    respuesta_proveedor: RespuestaAcceso,
    config: Optional[Configuracion] = None,
    adaptador: Optional[AdaptadorAutenticacion] = None,
    retorno_permitido: Optional[str] = None,
) -> Resultado[ContextoUsuario]:
    """Procesa el retorno OAuth de Google/Supabase, valida CSRF e intercambia el código por la identidad.

    Args:
        respuesta_proveedor: Parámetros devueltos por el proveedor (código, state o error).
        config: Configuración de la aplicación opcional.
        adaptador: Adaptador de autenticación inyectado opcional.
        retorno_permitido: URL de retorno registrada originalmente.

    Returns:
        Resultado[ContextoUsuario]: Identidad estable comprobada del usuario.
    """
    if respuesta_proveedor.error:
        mensaje_error = respuesta_proveedor.error_description or respuesta_proveedor.error
        return Resultado.fallo(
            codigo=CODIGO_ACCESO_DENEGADO,
            mensaje_usuario=f"El proveedor de autenticación reportó un error: {mensaje_error}",
        )

    if not respuesta_proveedor.code:
        return Resultado.fallo(
            codigo=CODIGO_ACCESO_DENEGADO,
            mensaje_usuario="No se recibió el código de autorización requerido del proveedor.",
        )

    adapt = _obtener_adaptador(config=config, adaptador=adaptador)
    if adapt is None:
        return Resultado.fallo(
            codigo=CODIGO_CONFIGURACION_INVALIDA,
            mensaje_usuario="El servicio de autenticación no está configurado.",
        )

    res_sesion = adapt.intercambiar_codigo(
        auth_code=respuesta_proveedor.code,
        state=respuesta_proveedor.state,
        redirect_to=retorno_permitido,
    )
    if not res_sesion.ok or not res_sesion.valor:
        return Resultado.fallo(error=res_sesion.error)

    return Resultado.exito(res_sesion.valor.contexto)


def obtener_usuario_actual(
    sesion_id: Optional[str] = None,
    config: Optional[Configuracion] = None,
    adaptador: Optional[AdaptadorAutenticacion] = None,
) -> Resultado[ContextoUsuario]:
    """Obtiene la identidad verificada del usuario actual a partir de su sesión activa.

    Si no se proporciona sesión o la sesión es inválida o expiró, rechaza la operación.
    Nunca habilita acceso ficticio silenciosamente ante fallos o ausencia de configuración.

    Args:
        sesion_id: Identificador / token de acceso de la sesión a comprobar.
        config: Configuración de la aplicación opcional.
        adaptador: Adaptador de autenticación inyectado opcional.

    Returns:
        Resultado[ContextoUsuario]: Identidad comprobada o error de sesión requerida.
    """
    if not sesion_id or not isinstance(sesion_id, str) or not sesion_id.strip():
        return Resultado.fallo(
            codigo=CODIGO_SESION_REQUERIDA,
            mensaje_usuario="No hay una sesión activa. Debes iniciar sesión con Google para acceder.",
        )

    cfg = config
    if cfg is None:
        res_cfg = cargar_configuracion()
        if res_cfg.ok and res_cfg.valor:
            cfg = res_cfg.valor

    # Manejo explícito y aislado del modo demostración local
    if sesion_id == ID_SESION_DEMO:
        if cfg and cfg.permitir_demo_local:
            return Resultado.exito(
                ContextoUsuario(
                    user_id=ID_USUARIO_DEMO,
                    sesion_id=ID_SESION_DEMO,
                    email="demo@homelens.local",
                    nombre="Usuario Demo (Local)",
                    es_demo=True,
                )
            )
        else:
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario="El modo demostración local no está autorizado en este entorno.",
            )

    adapt = _obtener_adaptador(config=cfg, adaptador=adaptador)
    if adapt is None:
        return Resultado.fallo(
            codigo=CODIGO_CONFIGURACION_INVALIDA,
            mensaje_usuario="No es posible verificar la sesión porque la configuración de autenticación está incompleta.",
        )

    return adapt.verificar_sesion(access_token=sesion_id)


def iniciar_acceso_demo(
    config: Optional[Configuracion] = None,
) -> Resultado[ContextoUsuario]:
    """Permite el ingreso en modo demostración local exclusivamente si está configurado en desarrollo.

    Nunca debe activarse silenciosamente cuando falle Google o Supabase.

    Args:
        config: Configuración de la aplicación opcional.

    Returns:
        Resultado[ContextoUsuario]: Contexto de usuario demo claramente diferenciado.
    """
    cfg = config
    if cfg is None:
        res_cfg = cargar_configuracion()
        if res_cfg.ok and res_cfg.valor:
            cfg = res_cfg.valor

    if not cfg or not cfg.permitir_demo_local:
        return Resultado.fallo(
            codigo=CODIGO_ACCESO_DENEGADO,
            mensaje_usuario="El modo de demostración local está deshabilitado en este entorno. Debe iniciar sesión con Google.",
        )

    return Resultado.exito(
        ContextoUsuario(
            user_id=ID_USUARIO_DEMO,
            sesion_id=ID_SESION_DEMO,
            email="demo@homelens.local",
            nombre="Usuario Demo (Local)",
            es_demo=True,
        )
    )


def cerrar_sesion(
    sesion_id: Optional[str] = None,
    config: Optional[Configuracion] = None,
    adaptador: Optional[AdaptadorAutenticacion] = None,
) -> Resultado[Confirmacion]:
    """Cierra la sesión activa en el proveedor y en el servidor.

    Args:
        sesion_id: Identificador / token de acceso de la sesión a revocar.
        config: Configuración de la aplicación opcional.
        adaptador: Adaptador de autenticación inyectado opcional.

    Returns:
        Resultado[Confirmacion]: Confirmación de la operación.
    """
    if sesion_id and sesion_id != ID_SESION_DEMO:
        adapt = _obtener_adaptador(config=config, adaptador=adaptador)
        if adapt is not None:
            adapt.cerrar_sesion(access_token=sesion_id)

    return Resultado.exito(
        Confirmacion(
            operacion_id=uuid4(),
            mensaje="Sesión cerrada correctamente. Credenciales y datos descartados.",
        )
    )
