"""M5: audio bajo demanda, caché volátil acotada y solicitudes deduplicadas."""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future, TimeoutError as TiempoEspera
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from hashlib import sha256
import math
import os
import re
from threading import RLock
from time import monotonic
import unicodedata
from uuid import UUID

from homelens.config import cargar_configuracion
from homelens.errores import (
    Resultado, CODIGO_CONFIGURACION_INVALIDA, CODIGO_SESION_REQUERIDA,
    CODIGO_RESPUESTA_INVALIDA, CODIGO_SERVICIO_NO_DISPONIBLE,
    CODIGO_TIEMPO_AGOTADO, CODIGO_LIMITE_ALCANZADO,
)
from homelens.integraciones.tts import (
    AdaptadorTTS, ErrorConfiguracionTTS, ErrorTiempoTTS,
)
from homelens.modelos import ContextoUsuario, SolicitudAudio, AudioDisponible

MAX_TEXTO_CARACTERES = 500
MAX_TEXTO_BYTES = 2000
MAX_ENTRADAS_SESION = 32
MAX_BYTES_SESION = 2 * 1024 * 1024
MAX_SESIONES = 64
MAX_BYTES_TOTAL = 16 * 1024 * 1024
MAX_BYTES_AUDIO = 512 * 1024
MAX_SOLICITUDES_EN_CURSO = 16

ClaveAudio = tuple[str, str, str, float]


@dataclass
class _Entrada:
    audio: AudioDisponible
    expira_en: float


@dataclass
class _CacheSesion:
    sesion_hash: str
    entradas: OrderedDict[ClaveAudio, _Entrada] = field(default_factory=OrderedDict)


_CACHE_AUDIO_SESION: OrderedDict[str, _CacheSesion] = OrderedDict()
_EN_CURSO: dict[tuple[str, ClaveAudio], Future] = {}
_CANDADO = RLock()


def _hash(texto: str) -> str:
    return sha256(texto.encode("utf-8")).hexdigest()


def _sesion_valida(usuario: ContextoUsuario) -> bool:
    return (
        isinstance(usuario, ContextoUsuario)
        and isinstance(usuario.user_id, UUID) and usuario.user_id.int != 0
        and isinstance(usuario.sesion_id, str)
        and 0 < len(usuario.sesion_id.strip()) <= 8192
        and not any(unicodedata.category(c).startswith("C") for c in usuario.sesion_id)
    )


def _solicitud_valida(solicitud: SolicitudAudio) -> bool:
    if not isinstance(solicitud, SolicitudAudio):
        return False
    texto = solicitud.texto
    return (
        isinstance(texto, str) and bool(texto.strip())
        and len(texto) <= MAX_TEXTO_CARACTERES
        and not any(unicodedata.category(c).startswith("C") or c in "<>" for c in texto)
        and len(texto.encode("utf-8")) <= MAX_TEXTO_BYTES
        and any(c.isalpha() for c in texto)
        and isinstance(solicitud.idioma, str)
        and re.fullmatch(r"en-[A-Z]{2}", solicitud.idioma) is not None
        and isinstance(solicitud.voz, str)
        and re.fullmatch(re.escape(solicitud.idioma) + r"-Standard-[A-Z]", solicitud.voz) is not None
        and type(solicitud.velocidad) in (int, float)
        and 0.25 <= solicitud.velocidad <= 2.0 and math.isfinite(solicitud.velocidad)
    )


def _claves(usuario: ContextoUsuario, solicitud: SolicitudAudio) -> tuple[str, ClaveAudio]:
    return (
        _hash(f"{usuario.user_id}:{_hash(usuario.sesion_id)}"),
        (solicitud.texto, solicitud.idioma, solicitud.voz, solicitud.velocidad),
    )


def _purgar() -> None:
    """Se ejecuta bajo candado; elimina vencidos de sesiones abandonadas."""
    ahora = monotonic()
    for cache in _CACHE_AUDIO_SESION.values():
        for clave in list(cache.entradas):
            if cache.entradas[clave].expira_en <= ahora:
                del cache.entradas[clave]


def _bytes(cache: _CacheSesion) -> int:
    return sum(len(e.audio.contenido) for e in cache.entradas.values())


def _acotar() -> None:
    for cache in _CACHE_AUDIO_SESION.values():
        while len(cache.entradas) > MAX_ENTRADAS_SESION or _bytes(cache) > MAX_BYTES_SESION:
            cache.entradas.popitem(last=False)
    while len(_CACHE_AUDIO_SESION) > MAX_SESIONES or sum(
        _bytes(c) for c in _CACHE_AUDIO_SESION.values()
    ) > MAX_BYTES_TOTAL:
        _CACHE_AUDIO_SESION.popitem(last=False)


def _consultar_audio_cache(
    usuario: ContextoUsuario, solicitud: SolicitudAudio,
) -> AudioDisponible | None:
    """Consulta sin síntesis para redibujar un reproductor después de un rerun."""
    if not _sesion_valida(usuario) or not _solicitud_valida(solicitud):
        return None
    namespace, clave = _claves(usuario, solicitud)
    with _CANDADO:
        _purgar()
        cache = _CACHE_AUDIO_SESION.get(namespace)
        entrada = cache.entradas.get(clave) if cache else None
        if entrada is None:
            return None
        cache.entradas.move_to_end(clave)
        _CACHE_AUDIO_SESION.move_to_end(namespace)
        return replace(entrada.audio, reutilizado=True)


def _crear_adaptador(usuario: ContextoUsuario) -> AdaptadorTTS:
    """Punto de inyección para simulaciones; el servicio real requiere opt-in."""
    if (
        os.getenv("GOOGLE_TTS_ENABLED", "false").strip().lower() != "true"
        or os.getenv("APP_ENV", "development").strip().lower() in {"test", "testing"}
        or usuario.es_demo or usuario.sesion_id == "local_demo_session"
    ):
        raise ErrorConfiguracionTTS("TTS real deshabilitado.")
    return AdaptadorTTS()


def obtener_audio(
    usuario: ContextoUsuario,
    solicitud: SolicitudAudio,
    operacion_id: UUID,
) -> Resultado[AudioDisponible]:
    """Sintetiza cuando la UI lo solicita mediante un botón.

    Recibe el contexto ya comprobado por M1. La UI usa un ámbito privado por
    navegador; no se consulta autenticación contra otro servicio desde M5.
    """
    def fallo(codigo, mensaje, reintentable=False):
        return Resultado.fallo(codigo=codigo, mensaje_usuario=mensaje,
                               reintentable=reintentable, operacion_id=operacion_id)

    if not _sesion_valida(usuario):
        return fallo(CODIGO_SESION_REQUERIDA, "Inicia sesión para solicitar audio.")
    if not _solicitud_valida(solicitud):
        return fallo(CODIGO_RESPUESTA_INVALIDA, "El contenido no es válido para pronunciación.")
    config = cargar_configuracion()
    if not config.ok or config.valor is None or config.valor.audio_cache_ttl_seconds <= 0:
        return fallo(CODIGO_CONFIGURACION_INVALIDA, "La configuración de audio no está disponible.")
    ttl = config.valor.audio_cache_ttl_seconds
    namespace, clave = _claves(usuario, solicitud)
    pendiente = (namespace, clave)
    with _CANDADO:
        audio = _consultar_audio_cache(usuario, solicitud)
        if audio is not None:
            return Resultado.exito(audio)
        futuro = _EN_CURSO.get(pendiente)
        es_generador = futuro is None
        if es_generador:
            if len(_EN_CURSO) >= MAX_SOLICITUDES_EN_CURSO:
                return fallo(CODIGO_LIMITE_ALCANZADO, "El audio está ocupado. Inténtalo en unos instantes.", True)
            cache = _CACHE_AUDIO_SESION.setdefault(namespace, _CacheSesion(_hash(usuario.sesion_id)))
            _CACHE_AUDIO_SESION.move_to_end(namespace)
            _acotar()
            futuro = Future()
            _EN_CURSO[pendiente] = futuro

    if not es_generador:
        try:
            resultado = futuro.result(timeout=12)
            if resultado.ok:
                return Resultado.exito(replace(resultado.valor, reutilizado=True))
            return Resultado.fallo(error=replace(resultado.error, operacion_id=operacion_id))
        except TiempoEspera:
            return fallo(CODIGO_TIEMPO_AGOTADO, "El audio tardó demasiado. Puedes volver a intentarlo.", True)

    try:
        contenido = _crear_adaptador(usuario).sintetizar(solicitud)
        if not isinstance(contenido, bytes) or not contenido or len(contenido) > MAX_BYTES_AUDIO:
            resultado = fallo(CODIGO_RESPUESTA_INVALIDA, "No se recibió un audio válido.", True)
        else:
            audio = AudioDisponible(contenido, "audio/mpeg", datetime.now(timezone.utc), False)
            resultado = Resultado.exito(audio)
    except ErrorConfiguracionTTS:
        resultado = fallo(CODIGO_CONFIGURACION_INVALIDA,
                          "La pronunciación todavía no está habilitada. Puedes seguir leyendo las tarjetas.")
    except (ErrorTiempoTTS, TimeoutError):
        resultado = fallo(CODIGO_TIEMPO_AGOTADO, "El audio tardó demasiado. Puedes volver a intentarlo.", True)
    except Exception:
        resultado = fallo(CODIGO_SERVICIO_NO_DISPONIBLE,
                          "La pronunciación no está disponible por el momento. Inténtalo más tarde.", True)

    with _CANDADO:
        # La limpieza durante la síntesis invalida también la respuesta pendiente.
        if _CACHE_AUDIO_SESION.get(namespace) is not cache:
            resultado = fallo(CODIGO_SESION_REQUERIDA, "La sesión de audio terminó. Vuelve a solicitarlo.")
        elif resultado.ok:
            cache.entradas[clave] = _Entrada(resultado.valor, monotonic() + ttl)
            _acotar()
        _EN_CURSO.pop(pendiente, None)
        futuro.set_result(resultado)
    return resultado


def limpiar_cache_audio(sesion_id: str) -> None:
    """Descarta audios y cancela su reinserción si hay una síntesis en curso."""
    if not isinstance(sesion_id, str):
        return
    sesion_hash = _hash(sesion_id)
    with _CANDADO:
        for namespace, cache in list(_CACHE_AUDIO_SESION.items()):
            if cache.sesion_hash == sesion_hash:
                del _CACHE_AUDIO_SESION[namespace]
