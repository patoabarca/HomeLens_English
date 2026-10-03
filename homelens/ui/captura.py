"""Componente de interfaz para captura y preparación de imágenes (M2)."""

from __future__ import annotations
import streamlit as st

from homelens.config import Configuracion
from homelens.imagenes import preparar_imagen, LIMITE_TAMANIO_BYTES_POR_DEFECTO
from homelens.ui.estado import (
    registrar_nueva_imagen,
    descartar_imagen_actual,
    invalidar_preparacion_anterior,
)


def renderizar_pantalla_captura(config: Configuracion) -> None:
    """Renderiza la interfaz de captura, carga, vista previa y preparación de imágenes."""
    st.header("📸 Captura y Preparación de Imágenes")
    st.caption("Módulo M2: Selecciona o toma una fotografía para prepararla para el análisis educativo.")

    # Aviso sobre tratamiento y privacidad de imágenes
    with st.expander("🔒 Tratamiento y Privacidad de Imágenes", expanded=False):
        st.markdown(
            """
            - **Procesamiento en memoria:** Las imágenes se validan y preparan temporalmente en la memoria de tu sesión.
            - **Sin persistencia:** Tus fotografías **no se almacenan** en bases de datos, repositorios ni registros del servidor.
            - **Saneamiento automático:** Se eliminan metadatos EXIF privados (como ubicación GPS o modelo de cámara) y se corrige la orientación.
            """
        )

    # Selector claro de origen de imagen
    col_orig, col_info = st.columns([2, 1])
    with col_orig:
        origen_seleccionado = st.radio(
            "Selecciona el método de entrada:",
            options=["Subir archivo (JPEG / PNG)", "Usar cámara web / móvil"],
            index=0 if st.session_state.origen_imagen == "archivo" else 1,
            horizontal=True,
            help="Elige si deseas cargar una imagen desde tu dispositivo o tomar una fotografía en vivo.",
        )
    with col_info:
        limite_mb = config.max_image_size_bytes / 1_000_000
        st.info(f"📏 Límite máximo: **{limite_mb:g} MB**\n\nFormatos: **JPEG / PNG**")

    nuevo_origen = "archivo" if "archivo" in origen_seleccionado.lower() else "camara"

    # Si el usuario cambió de pestaña de origen, registrar
    if st.session_state.origen_imagen != nuevo_origen:
        st.session_state.origen_imagen = nuevo_origen

    bytes_capturados: bytes | None = None

    # Controles según origen seleccionado
    if nuevo_origen == "archivo":
        archivo_subido = st.file_uploader(
            "Selecciona una imagen de tu dispositivo:",
            type=["jpg", "jpeg", "png"],
            key="uploader_archivo_imagen",
            help="Archivos admitidos: .jpg, .jpeg, .png",
        )
        if archivo_subido is not None:
            bytes_capturados = archivo_subido.getvalue()
    else:
        foto_camara = st.camera_input(
            "Toma una fotografía con tu cámara:",
            key="captura_camara_imagen",
            help="Asegúrate de permitir el acceso a la cámara en tu navegador.",
        )
        if foto_camara is not None:
            bytes_capturados = foto_camara.getvalue()

    # Si hay nuevos bytes, registrar e invalidar preparación anterior si corresponde
    if bytes_capturados is not None:
        registrar_nueva_imagen(bytes_capturados, nuevo_origen)

    # Sección de visualización y acciones
    if st.session_state.imagen_cargada_bytes:
        st.divider()
        st.subheader("🖼️ Vista Previa y Estado")

        col_img, col_acciones = st.columns([3, 2])

        with col_img:
            # Mostrar la imagen con la orientación y proporción adecuada
            st.image(
                st.session_state.imagen_cargada_bytes,
                caption="Imagen seleccionada (Original)",
                use_container_width=True,
            )

        with col_acciones:
            st.markdown("### Acciones de Preparación")

            # Botón explícito para preparar la imagen
            if st.button("⚙️ Preparar Imagen", type="primary", use_container_width=True):
                with st.spinner("Validando, corrigiendo orientación y preparando imagen..."):
                    resultado = preparar_imagen(
                        contenido=st.session_state.imagen_cargada_bytes,
                        max_bytes=config.max_image_size_bytes,
                    )

                    if resultado.ok and resultado.valor is not None:
                        st.session_state.imagen_preparada = resultado.valor
                        st.session_state.error_preparacion = None
                    else:
                        st.session_state.imagen_preparada = None
                        st.session_state.error_preparacion = (
                            resultado.error.mensaje_usuario
                            if resultado.error
                            else "Error desconocido al procesar la imagen."
                        )

            # Botón para descartar y liberar
            if st.button("🗑️ Quitar / Reemplazar Imagen", use_container_width=True):
                descartar_imagen_actual()
                st.rerun()

            # Feedback de estado de preparación
            if st.session_state.imagen_preparada is not None:
                prep = st.session_state.imagen_preparada
                st.success("✅ **Imagen preparada exitosamente**")
                st.markdown(
                    f"""
                    - **Dimensiones:** `{prep.ancho} × {prep.alto} px`
                    - **Tipo MIME:** `{prep.mime_type}`
                    - **Tamaño procesado:** `{len(prep.contenido) / 1024:.1f} KB`
                    - **Estado:** Lista en memoria para integración con Gemini (Paso 3).
                    """
                )
                st.caption(
                    "ℹ️ *Nota pedagógica:* En esta etapa no se realizan llamadas a Gemini ni se generan etiquetas simuladas sobre tu imagen."
                )

            elif st.session_state.error_preparacion:
                st.error(f"❌ {st.session_state.error_preparacion}")
            else:
                st.info("ℹ️ Presiona **'⚙️ Preparar Imagen'** para validar formato, orientación y dimensiones antes del análisis.")

    else:
        st.divider()
        st.info("👆 Selecciona un archivo o toma una fotografía con tu cámara para comenzar.")
