"""Controles de pronunciación independientes de Gemini y de los cuestionarios."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import inspect
from uuid import uuid4

import streamlit as st

from homelens.audio import obtener_audio, limpiar_cache_audio, _consultar_audio_cache
from homelens.config import cargar_configuracion
from homelens.modelos import (
    ContextoUsuario, Exploracion, ObjetoEducativo, SolicitudAudio, EstadoAnalisis,
)

OPCIONES_VELOCIDAD_FRASE: dict[str, float] = {
    "Normal (1.0x)": 1.0,
    "Lenta (0.8x)": 0.8,
    "Muy lenta (0.65x)": 0.65,
}
VELOCIDAD_FRASE_DEFECTO: str = "Lenta (0.8x)"
VELOCIDAD_PALABRA: float = 1.0
CLAVE_VELOCIDAD_FRASE: str = "_audio_velocidad_frase"


def _cb_cambio_velocidad(key_origen: str) -> None:
    """Propaga el cambio de velocidad al estado global y a los widgets de la sesión."""
    opcion = st.session_state.get(key_origen)
    if opcion in OPCIONES_VELOCIDAD_FRASE:
        st.session_state[CLAVE_VELOCIDAD_FRASE] = opcion
        for k in list(st.session_state.keys()):
            if k.startswith("audio_") and k.endswith("_velocidad"):
                st.session_state[k] = opcion


def limpiar_audio_sesion_ui() -> None:
    """Libera el ámbito privado y toda selección de reproductor de este navegador."""
    contexto = st.session_state.pop("_audio_contexto", None)
    if contexto is not None:
        limpiar_cache_audio(contexto.sesion_id)
    for clave in (
        "_audio_identidad",
        "_audio_exploracion",
        "_audio_selecciones",
        CLAVE_VELOCIDAD_FRASE,
    ):
        st.session_state.pop(clave, None)
    for clave in list(st.session_state.keys()):
        if clave.startswith("audio_") and clave.endswith("_velocidad"):
            st.session_state.pop(clave, None)


def _contexto_audio(usuario: ContextoUsuario) -> ContextoUsuario:
    # No retener el token de autenticación en una segunda copia del contexto.
    identidad = sha256(
        f"{usuario.user_id}:{usuario.sesion_id}:{usuario.es_demo}".encode("utf-8")
    ).hexdigest()
    if st.session_state.get("_audio_identidad") != identidad:
        limpiar_audio_sesion_ui()
        st.session_state["_audio_identidad"] = identidad
        st.session_state["_audio_contexto"] = replace(
            usuario, sesion_id=f"audio:{uuid4()}", email=None, nombre=None,
        )
    return st.session_state["_audio_contexto"]


def mostrar_controles_audio(exploracion: Exploracion, objeto: ObjetoEducativo) -> None:
    """Solo los botones solicitan síntesis; redibujar consulta únicamente la caché."""
    usuario = st.session_state.get("usuario")
    if (
        not isinstance(usuario, ContextoUsuario) or not usuario.sesion_id
        or usuario.user_id != exploracion.user_id
        or exploracion.estado != EstadoAnalisis.UTILIZABLE
        or st.session_state.get("exploracion_actual") != exploracion
        or objeto.exploracion_id != exploracion.exploracion_id
        or objeto not in exploracion.objetos
    ):
        limpiar_audio_sesion_ui()
        st.caption("La pronunciación requiere una exploración de tu sesión activa.")
        return

    contexto = _contexto_audio(usuario)
    if st.session_state.get("_audio_exploracion") != exploracion.exploracion_id:
        st.session_state["_audio_exploracion"] = exploracion.exploracion_id
        st.session_state["_audio_selecciones"] = {}
    selecciones = st.session_state["_audio_selecciones"]

    prefijo = f"audio_{exploracion.exploracion_id}_{objeto.objeto_id}"

    # Sincronización de velocidad de frase en la sesión y entre tarjetas
    vel_actual = st.session_state.get(CLAVE_VELOCIDAD_FRASE, VELOCIDAD_FRASE_DEFECTO)
    key_vel = f"{prefijo}_velocidad"
    if st.session_state.get(key_vel) != vel_actual:
        st.session_state[key_vel] = vel_actual

    palabra, frase = st.columns(2)
    with palabra:
        pedir_palabra = st.button(
            "🔊 Escuchar palabra", key=f"{prefijo}_palabra",
            help="Prepara la pronunciación del nombre en inglés a velocidad normal (1.0x).",
            use_container_width=True,
        )
    with frase:
        pedir_frase = st.button(
            "🔊 Escuchar frase", key=f"{prefijo}_frase",
            help="Prepara la pronunciación de la frase en inglés a la velocidad seleccionada.",
            use_container_width=True,
        )

    # Selector de velocidad compacto para frases pedagógicas
    opciones_vel = list(OPCIONES_VELOCIDAD_FRASE.keys())
    if hasattr(st, "segmented_control"):
        st.segmented_control(
            "⚡ Velocidad de frase:",
            options=opciones_vel,
            key=key_vel,
            on_change=_cb_cambio_velocidad,
            args=(key_vel,),
            help="Ajusta la velocidad para escuchar la frase en inglés (Normal, Lenta o Muy lenta).",
        )
    else:
        st.radio(
            "⚡ Velocidad de frase:",
            options=opciones_vel,
            key=key_vel,
            horizontal=True,
            on_change=_cb_cambio_velocidad,
            args=(key_vel,),
            help="Ajusta la velocidad para escuchar la frase en inglés (Normal, Lenta o Muy lenta).",
        )

    if pedir_palabra or pedir_frase:
        # El texto sale del objeto validado, nunca de un campo libre del navegador.
        texto = objeto.nombre_en if pedir_palabra else objeto.frase_en
        vel_opcion = st.session_state.get(CLAVE_VELOCIDAD_FRASE, VELOCIDAD_FRASE_DEFECTO)
        velocidad = VELOCIDAD_PALABRA if pedir_palabra else OPCIONES_VELOCIDAD_FRASE.get(vel_opcion, 0.8)

        config = cargar_configuracion()
        if not config.ok or config.valor is None:
            st.warning("La pronunciación no está disponible por el momento.")
            return
        solicitud = SolicitudAudio(
            texto=texto, idioma=config.valor.google_tts_language_code,
            voz=config.valor.google_tts_voice_name, velocidad=velocidad,
        )
        with st.spinner("Preparando pronunciación…"):
            resultado = obtener_audio(contexto, solicitud, uuid4())
        if not resultado.ok:
            st.warning(resultado.error.mensaje_usuario)
            return
        selecciones[objeto.objeto_id] = solicitud

    solicitud = selecciones.get(objeto.objeto_id)
    if solicitud is None:
        return
    audio = _consultar_audio_cache(contexto, solicitud)
    if audio is None:
        selecciones.pop(objeto.objeto_id, None)
        st.caption("El audio temporal ya no está disponible. Pulsa Escuchar para prepararlo otra vez.")
        return
    etiqueta_tipo = f"frase ({solicitud.velocidad}x)" if solicitud.texto == objeto.frase_en else "palabra (1.0x)"
    st.caption(f"Audio listo · {etiqueta_tipo}. Pulsa ▶ para escuchar; puedes repetirlo desde el reproductor.")
    # alt es reciente: mantener compatibilidad con el mínimo de Streamlit del repo.
    accesibilidad = {"alt": "Pronunciación del contenido educativo en inglés"} if (
        "alt" in inspect.signature(st.audio).parameters
    ) else {}
    st.audio(audio.contenido, format=audio.mime_type, autoplay=False, **accesibilidad)
