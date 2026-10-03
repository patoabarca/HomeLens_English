"""HomeLens English - Aplicación Principal.

Punto de entrada de Streamlit y orquestación inicial de módulos M0-M8.
"""

from __future__ import annotations
import streamlit as st

from homelens.config import cargar_configuracion
from homelens.acceso import obtener_usuario_actual
from homelens.ui.estado import inicializar_estado_sesion


def main() -> None:
    st.set_page_config(
        page_title="HomeLens English",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inicializar_estado_sesion()

    # Cargar configuración del sistema (M0)
    res_config = cargar_configuracion()
    if not res_config.ok or res_config.valor is None:
        st.error(f"Error de configuración: {res_config.error.mensaje_usuario if res_config.error else 'Desconocido'}")
        st.stop()

    config = res_config.valor

    # Obtener usuario actual (M1)
    res_usuario = obtener_usuario_actual()
    if res_usuario.ok and res_usuario.valor:
        st.session_state.usuario = res_usuario.valor

    # Sidebar: Estado del Sistema y Navegación
    with st.sidebar:
        st.title("🔍 HomeLens English")
        st.caption("Aprende inglés explorando tu entorno con IA")
        st.divider()

        seccion = st.radio(
            "Navegación",
            ["Inicio / Estado", "Exploración Visual", "Prácticas y Cuestionarios", "Desafíos Find It", "Mi Progreso"],
            index=0,
        )

        st.divider()
        st.subheader("Estado de Integraciones")
        st.write(f"• **Entorno:** `{config.app_env}`")
        st.write(f"• **Gemini API:** {'🟢 Configurado' if config.tiene_gemini else '🟡 Pendiente (.env)'}")
        st.write(f"• **Supabase:** {'🟢 Configurado' if config.tiene_supabase else '🟡 Pendiente (.env)'}")
        st.write(f"• **TTS Idioma:** `{config.google_tts_language_code}`")

    # Contenido Principal
    if seccion == "Inicio / Estado":
        st.header("Bienvenido a HomeLens English")
        st.markdown(
            """
            **HomeLens English** es un asistente educativo inteligente diseñado para transformar objetos cotidianos
            en oportunidades de aprendizaje de vocabulario y gramática en inglés.

            ### Estado de la Entrega 1:
            - ✅ **M0 Configuración y Entorno:** Validado y cargado de forma segura.
            - ✅ **Estructuras y Modelos de Dominio:** Definidos e inmutables (M0-M8).
            - ✅ **Manejo de Errores e Invariantes:** Contenedor `Resultado[T]` y `ErrorOperacion` implementados.
            - ✅ **Aislamiento de Secretos:** Exclusión estricta de credenciales en `.gitignore` y plantilla `.env.example`.
            - ✅ **Entorno Docker:** `Dockerfile`, `compose.yaml` y `.dockerignore` configurados.
            """
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Módulos Diseñados", value="M0 - M8")
        with col2:
            st.metric(label="Límite Tamaño Imagen", value=f"{config.max_image_size_bytes // 1_000_000} MB")
        with col3:
            st.metric(label="Modelo Gemini Previsto", value=config.gemini_model)

    elif seccion == "Exploración Visual":
        st.header("📸 Exploración Visual")
        st.info("El módulo de captura y análisis interactivo con Gemini estará disponible a partir del Paso 2.")
        uploaded_file = st.file_uploader("Subir imagen de prueba (JPEG / PNG)", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            st.image(uploaded_file, caption="Vista previa de imagen cargada", use_column_width=True)

    elif seccion == "Prácticas y Cuestionarios":
        st.header("📝 Prácticas y Cuestionarios")
        st.info("Los cuestionarios interactivos basados en tus exploraciones se activarán en los siguientes pasos.")

    elif seccion == "Desafíos Find It":
        st.header("🎯 Desafíos Find It")
        st.info("El módulo de desafíos interactivos por categoría se activará en los siguientes pasos.")

    elif seccion == "Mi Progreso":
        st.header("📊 Mi Progreso")
        st.info("Tu historial de palabras exploradas y estadísticas de práctica se mostrarán aquí.")


if __name__ == "__main__":
    main()
