"""Gestión del estado de sesión de Streamlit para HomeLens English."""

from __future__ import annotations
from typing import Optional
import streamlit as st

from homelens.modelos import ContextoUsuario, Exploracion, ImagenPreparada
from homelens.imagenes import liberar_imagen


def inicializar_estado_sesion() -> None:
    """Inicializa las claves necesarias en st.session_state si no existen."""
    if "usuario" not in st.session_state:
        st.session_state.usuario = None
    if "origen_imagen" not in st.session_state:
        st.session_state.origen_imagen = "archivo"
    if "imagen_cargada_bytes" not in st.session_state:
        st.session_state.imagen_cargada_bytes = None
    if "imagen_preparada" not in st.session_state:
        st.session_state.imagen_preparada = None
    if "error_preparacion" not in st.session_state:
        st.session_state.error_preparacion = None
    if "exploracion_actual" not in st.session_state:
        st.session_state.exploracion_actual = None
    if "intento_activo_id" not in st.session_state:
        st.session_state.intento_activo_id = None
    if "operacion_en_curso" not in st.session_state:
        st.session_state.operacion_en_curso = False
    if "uploader_version" not in st.session_state:
        st.session_state.uploader_version = 0
    if "camera_version" not in st.session_state:
        st.session_state.camera_version = 0


def invalidar_preparacion_anterior() -> None:
    """Invalida la imagen preparada previa y cualquier resultado asociado."""
    if st.session_state.imagen_preparada is not None:
        liberar_imagen(st.session_state.imagen_preparada)
    st.session_state.imagen_preparada = None
    st.session_state.error_preparacion = None
    st.session_state.exploracion_actual = None
    st.session_state.intento_activo_id = None


def registrar_nueva_imagen(contenido: Optional[bytes], origen: str) -> None:
    """Registra nuevos bytes de imagen e invalida preparaciones anteriores si cambió el contenido."""
    if st.session_state.imagen_cargada_bytes != contenido:
        invalidar_preparacion_anterior()
        st.session_state.imagen_cargada_bytes = contenido
        st.session_state.origen_imagen = origen


def descartar_imagen_actual() -> None:
    """Descarta y libera completamente la imagen actual y reinicia los widgets de captura."""
    if st.session_state.imagen_preparada is not None:
        liberar_imagen(st.session_state.imagen_preparada)
    st.session_state.imagen_cargada_bytes = None
    st.session_state.imagen_preparada = None
    st.session_state.error_preparacion = None
    st.session_state.exploracion_actual = None
    st.session_state.intento_activo_id = None
    st.session_state.operacion_en_curso = False
    # Incrementar versiones de widgets para forzar el reseteo limpio en Streamlit
    st.session_state.uploader_version = st.session_state.get("uploader_version", 0) + 1
    st.session_state.camera_version = st.session_state.get("camera_version", 0) + 1


def limpiar_estado_sesion() -> None:
    """Limpia todos los datos temporales de la sesión actual."""
    descartar_imagen_actual()
