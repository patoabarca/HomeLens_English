"""Gestión del estado de sesión de Streamlit para HomeLens English."""

from __future__ import annotations
from typing import Optional
import streamlit as st

from homelens.modelos import ContextoUsuario, Exploracion, ImagenPreparada


def inicializar_estado_sesion() -> None:
    """Inicializa las claves necesarias en st.session_state si no existen."""
    if "usuario" not in st.session_state:
        st.session_state.usuario = None
    if "imagen_activa" not in st.session_state:
        st.session_state.imagen_activa = None
    if "exploracion_actual" not in st.session_state:
        st.session_state.exploracion_actual = None
    if "intento_activo_id" not in st.session_state:
        st.session_state.intento_activo_id = None
    if "operacion_en_curso" not in st.session_state:
        st.session_state.operacion_en_curso = False


def limpiar_estado_sesion() -> None:
    """Limpia los datos temporales de la sesión actual."""
    st.session_state.imagen_activa = None
    st.session_state.exploracion_actual = None
    st.session_state.intento_activo_id = None
    st.session_state.operacion_en_curso = False
