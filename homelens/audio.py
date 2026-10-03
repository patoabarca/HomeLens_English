"""Módulo M5: Generación y caché de audio (TTS)."""

from __future__ import annotations
from typing import Dict
from uuid import UUID
from datetime import datetime, timezone

from homelens.errores import Resultado, CODIGO_SERVICIO_NO_DISPONIBLE
from homelens.modelos import (
    ContextoUsuario,
    SolicitudAudio,
    AudioDisponible,
)

# Caché en memoria por sesión
_CACHE_AUDIO_SESION: Dict[str, Dict[str, AudioDisponible]] = {}


def obtener_audio(
    usuario: ContextoUsuario,
    solicitud: SolicitudAudio,
    operacion_id: UUID,
) -> Resultado[AudioDisponible]:
    """Obtiene el audio sintetizado, utilizando la caché de sesión si está disponible."""
    clave_cache = f"{solicitud.texto}_{solicitud.idioma}_{solicitud.voz}_{solicitud.velocidad}"
    
    if usuario.sesion_id in _CACHE_AUDIO_SESION:
        if clave_cache in _CACHE_AUDIO_SESION[usuario.sesion_id]:
            audio = _CACHE_AUDIO_SESION[usuario.sesion_id][clave_cache]
            return Resultado.exito(
                AudioDisponible(
                    contenido=audio.contenido,
                    mime_type=audio.mime_type,
                    generado_en=audio.generado_en,
                    reutilizado=True,
                )
            )

    return Resultado.fallo(
        codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
        mensaje_usuario="El servicio de audio TTS se activará en el Paso 5.",
        operacion_id=operacion_id,
    )


def limpiar_cache_audio(sesion_id: str) -> None:
    """Limpia la caché de audio de la sesión indicada."""
    if sesion_id in _CACHE_AUDIO_SESION:
        del _CACHE_AUDIO_SESION[sesion_id]
