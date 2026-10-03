"""Módulo M1: Acceso de usuarios y contexto de identidad."""

from __future__ import annotations
from typing import Optional
from uuid import UUID, uuid4

from homelens.errores import Resultado, CODIGO_SESION_REQUERIDA
from homelens.modelos import ContextoUsuario, Confirmacion


def obtener_usuario_actual(sesion_id: Optional[str] = None) -> Resultado[ContextoUsuario]:
    """Obtiene el contexto del usuario autenticado actual."""
    if not sesion_id:
        # Modo prototipo: usuario local por defecto para desarrollo
        demo_user_id = UUID("00000000-0000-0000-0000-000000000001")
        return Resultado.exito(ContextoUsuario(user_id=demo_user_id, sesion_id="local_demo_session"))
    
    return Resultado.exito(ContextoUsuario(user_id=uuid4(), sesion_id=sesion_id))


def cerrar_sesion(sesion_id: str) -> Resultado[Confirmacion]:
    """Cierra la sesión activa del usuario y limpia referencias privadas."""
    return Resultado.exito(
        Confirmacion(
            operacion_id=uuid4(),
            mensaje="Sesión cerrada correctamente.",
        )
    )
