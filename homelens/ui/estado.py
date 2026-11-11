"""Gestión del estado de sesión de Streamlit para HomeLens English.

Centraliza la inicialización de claves en memoria, la coherencia de datos
entre captura, análisis y visualización pedagógica, y la función reutilizable
de limpieza para la integración con autenticación (Tarea 5).
"""

from __future__ import annotations
from typing import Optional, Any
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
    if "objeto_seleccionado_id" not in st.session_state:
        st.session_state.objeto_seleccionado_id = None
    if "scroll_hacia_foto" not in st.session_state:
        st.session_state.scroll_hacia_foto = False
    if "error_analisis" not in st.session_state:
        st.session_state.error_analisis = None
    if "imagen_asociada_id" not in st.session_state:
        st.session_state.imagen_asociada_id = None
    if "intento_activo_id" not in st.session_state:
        st.session_state.intento_activo_id = None
    if "operacion_en_curso" not in st.session_state:
        st.session_state.operacion_en_curso = False
    if "uploader_version" not in st.session_state:
        st.session_state.uploader_version = 0
    if "camera_version" not in st.session_state:
        st.session_state.camera_version = 0
    if "error_auth" not in st.session_state:
        st.session_state.error_auth = None
    if "mensaje_auth" not in st.session_state:
        st.session_state.mensaje_auth = None
    if "seccion_navegacion" not in st.session_state:
        st.session_state.seccion_navegacion = "Inicio / Estado"
    # Estado del historial de exploraciones (M7 - Tarea 7)
    if "exploraciones_guardadas_ids" not in st.session_state:
        st.session_state.exploraciones_guardadas_ids = set()
    if "_exploraciones_demo" not in st.session_state:
        st.session_state._exploraciones_demo = {}
    if "mensaje_historial" not in st.session_state:
        st.session_state.mensaje_historial = None
    if "error_historial" not in st.session_state:
        st.session_state.error_historial = None
    if "exploracion_en_vista_historial" not in st.session_state:
        st.session_state.exploracion_en_vista_historial = None
    # Estado de cuestionarios pedagógicos (M6 - Tarea 9)
    if "cuestionario_indice_actual" not in st.session_state:
        st.session_state.cuestionario_indice_actual = 0
    if "cuestionario_respuestas" not in st.session_state:
        st.session_state.cuestionario_respuestas = {}
    if "cuestionario_opciones_elegidas" not in st.session_state:
        st.session_state.cuestionario_opciones_elegidas = {}
    if "cuestionario_orden_opciones" not in st.session_state:
        st.session_state.cuestionario_orden_opciones = {}
    if "cuestionario_confirmado" not in st.session_state:
        st.session_state.cuestionario_confirmado = False
    if "cuestionario_exploracion_id" not in st.session_state:
        st.session_state.cuestionario_exploracion_id = None
    if "cuestionario_finalizado" not in st.session_state:
        st.session_state.cuestionario_finalizado = False


def limpiar_datos_cuestionario() -> None:
    """Restablece completamente el progreso, respuestas, órdenes e índice del cuestionario activo."""
    st.session_state.cuestionario_indice_actual = 0
    st.session_state.cuestionario_respuestas = {}
    st.session_state.cuestionario_opciones_elegidas = {}
    st.session_state.cuestionario_orden_opciones = {}
    st.session_state.cuestionario_confirmado = False
    st.session_state.cuestionario_exploracion_id = None
    st.session_state.cuestionario_finalizado = False

    # Eliminar claves dinámicas de selección de widgets para forzar deselección limpia
    for k in list(st.session_state.keys()):
        if str(k).startswith("radio_actividad_"):
            del st.session_state[k]


def limpiar_datos_exploracion() -> None:
    """Limpia la fotografía temporal, la exploración activa, la selección y errores.

    Función reutilizable y centralizada para:
    1. Descartar la imagen activa y liberar memoria (M2).
    2. Invalidar la exploración de Gemini y sus actividades (M3/M4).
    3. Reiniciar la selección de objeto enfocado y la imagen anotada (M4).
    4. Limpiar los audios sintetizados de sesión (M5 - Victoria).
    5. Limpiar el estado y respuestas de cuestionarios (M6 - Patricia).
    6. Permitir que la Tarea 5 (Autenticación de Lucas) limpie todos los datos
       privados al cerrar sesión, al expirar el token o al cambiar de usuario.
    """
    from homelens.ui.audio import limpiar_audio_sesion_ui
    limpiar_audio_sesion_ui()
    if st.session_state.get("imagen_preparada") is not None:
        liberar_imagen(st.session_state.imagen_preparada)
    st.session_state.imagen_cargada_bytes = None
    st.session_state.imagen_preparada = None
    st.session_state.error_preparacion = None
    st.session_state.exploracion_actual = None
    st.session_state.exploracion_en_vista_historial = None
    st.session_state.objeto_seleccionado_id = None
    st.session_state.error_analisis = None
    st.session_state.imagen_asociada_id = None
    st.session_state.scroll_hacia_foto = False
    st.session_state.intento_activo_id = None
    st.session_state.operacion_en_curso = False
    limpiar_datos_cuestionario()


def invalidar_preparacion_anterior() -> None:
    """Invalida la imagen preparada previa y cualquier resultado asociado."""
    if st.session_state.get("imagen_preparada") is not None:
        liberar_imagen(st.session_state.imagen_preparada)
    st.session_state.imagen_preparada = None
    st.session_state.error_preparacion = None
    st.session_state.exploracion_actual = None
    st.session_state.exploracion_en_vista_historial = None
    st.session_state.objeto_seleccionado_id = None
    st.session_state.scroll_hacia_foto = False
    st.session_state.error_analisis = None
    st.session_state.imagen_asociada_id = None
    st.session_state.intento_activo_id = None
    limpiar_datos_cuestionario()


def registrar_nueva_imagen(contenido: Optional[bytes], origen: str) -> None:
    """Registra nuevos bytes de imagen e invalida preparaciones anteriores si cambió el contenido."""
    if st.session_state.imagen_cargada_bytes != contenido:
        invalidar_preparacion_anterior()
        st.session_state.imagen_cargada_bytes = contenido
        st.session_state.origen_imagen = origen


def descartar_imagen_actual() -> None:
    """Descarta y libera completamente la imagen actual y reinicia los widgets de captura."""
    limpiar_datos_exploracion()
    # Incrementar versiones de widgets para forzar el reseteo limpio en Streamlit
    st.session_state.uploader_version = st.session_state.get("uploader_version", 0) + 1
    st.session_state.camera_version = st.session_state.get("camera_version", 0) + 1


def limpiar_estado_sesion() -> None:
    """Limpia todos los datos temporales de la sesión actual."""
    descartar_imagen_actual()


def cerrar_sesion_usuario(config: Optional[Any] = None) -> None:
    """Cierra la sesión activa del usuario, invalida tokens y limpia datos temporales."""
    # Descartar el audio incluso si la revocación remota encuentra un error.
    from homelens.ui.audio import limpiar_audio_sesion_ui
    limpiar_audio_sesion_ui()
    usuario_actual = st.session_state.get("usuario")
    sesion_id = usuario_actual.sesion_id if usuario_actual else None

    from homelens.acceso import cerrar_sesion as ejecutar_cerrar_sesion
    ejecutar_cerrar_sesion(sesion_id=sesion_id, config=config)

    # Limpiar todos los datos de imagen, exploración y selecciones
    limpiar_datos_exploracion()

    # Descartar referencias al usuario
    st.session_state.usuario = None
    st.session_state.error_auth = None
    st.session_state.mensaje_auth = "Has cerrado sesión correctamente. Tus datos temporales fueron descartados."
    st.session_state.seccion_navegacion = "Inicio / Estado"
    st.session_state._exploraciones_demo = {}
    st.session_state.exploraciones_guardadas_ids = set()
    st.session_state.exploracion_en_vista_historial = None
    st.session_state.mensaje_historial = None
    st.session_state.error_historial = None

    # Forzar reinicio de widgets de entrada
    st.session_state.uploader_version = st.session_state.get("uploader_version", 0) + 1
    st.session_state.camera_version = st.session_state.get("camera_version", 0) + 1
