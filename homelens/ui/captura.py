"""Componente de interfaz para captura, preparación (M2) y orquestación de exploración."""

from __future__ import annotations
from uuid import uuid4
import streamlit as st

from homelens.config import Configuracion
from homelens.imagenes import preparar_imagen
from homelens.analisis import analizar_exploracion
from homelens.ui.estado import (
    registrar_nueva_imagen,
    descartar_imagen_actual,
)
from homelens.ui.exploracion import mostrar_exploracion


def renderizar_pantalla_captura(config: Configuracion) -> None:
    """Renderiza la interfaz de captura, carga, vista previa y análisis educativo."""
    st.header("📸 Captura y Exploración de Fotografías")
    st.caption("Selecciona o toma una fotografía de tu entorno para descubrir y aprender vocabulario en inglés.")

    # Aviso sobre tratamiento y privacidad de imágenes
    with st.expander("🔒 Tratamiento y Privacidad de Imágenes", expanded=False):
        st.markdown(
            """
            - **Procesamiento temporal en memoria:** Las imágenes se procesan exclusivamente en la memoria de tu sesión.
            - **Sin almacenamiento permanente:** Tus fotografías **no se guardan** en bases de datos ni en el servidor.
            - **Saneamiento automático:** Se corrigen giros EXIF y se remueven datos privados de ubicación antes del análisis.
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

    # Claves dinámicas vinculadas a la versión de estado para permitir reseteo limpio
    uploader_key = f"uploader_archivo_{st.session_state.get('uploader_version', 0)}"
    camera_key = f"captura_camara_{st.session_state.get('camera_version', 0)}"

    # Controles según origen seleccionado
    if nuevo_origen == "archivo":
        archivo_subido = st.file_uploader(
            "Selecciona una imagen de tu dispositivo:",
            type=["jpg", "jpeg", "png"],
            key=uploader_key,
            help="Archivos admitidos: .jpg, .jpeg, .png",
        )
        if archivo_subido is not None:
            bytes_capturados = archivo_subido.getvalue()
    else:
        foto_camara = st.camera_input(
            "Toma una fotografía con tu cámara:",
            key=camera_key,
            help="Asegúrate de permitir el acceso a la cámara en tu navegador.",
        )
        if foto_camara is not None:
            bytes_capturados = foto_camara.getvalue()

    # Si hay nuevos bytes, registrar e invalidar preparación y exploración previa
    if bytes_capturados is not None:
        registrar_nueva_imagen(bytes_capturados, nuevo_origen)

    # Sección de visualización y acciones de captura
    if st.session_state.imagen_cargada_bytes:
        # Solo mostrar el bloque de preparación si aún no hay exploración activa
        # o si el usuario desea revisar la imagen original
        with st.expander("⚙️ Gestión y Preparación de Imagen", expanded=(st.session_state.exploracion_actual is None)):
            col_img, col_acciones = st.columns([3, 2])

            with col_img:
                imagen_a_mostrar = (
                    st.session_state.imagen_preparada.contenido
                    if st.session_state.imagen_preparada is not None
                    else st.session_state.imagen_cargada_bytes
                )
                caption_texto = (
                    "Imagen Preparada (Orientación corregida y metadatos saneados)"
                    if st.session_state.imagen_preparada is not None
                    else "Imagen seleccionada (Original)"
                )
                st.image(
                    imagen_a_mostrar,
                    caption=caption_texto,
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
                            max_dimension_px=1280,
                        )

                        if resultado.ok and resultado.valor is not None:
                            st.session_state.imagen_preparada = resultado.valor
                            st.session_state.error_preparacion = None
                            st.rerun()
                        else:
                            st.session_state.imagen_preparada = None
                            st.session_state.error_preparacion = (
                                resultado.error.mensaje_usuario
                                if resultado.error
                                else "Error desconocido al procesar la imagen."
                            )
                            st.rerun()

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
                        """
                    )

                    st.divider()
                    st.markdown("### 🤖 Análisis Educativo")

                    if not config.tiene_gemini:
                        st.warning("⚠️ Clave `GEMINI_API_KEY` no configurada en `.env`.")
                    else:
                        st.success(f"🟢 Gemini API configurada (`{config.gemini_model}`)")

                    if st.button("🔍 Analizar Fotografía con IA", type="primary", use_container_width=True):
                        with st.spinner("Identificando objetos educativos con Gemini..."):
                            # Limpiar estados de análisis previos antes de iniciar nuevo intento
                            st.session_state.exploracion_actual = None
                            st.session_state.error_analisis = None
                            st.session_state.objeto_seleccionado_id = None

                            res_analisis = analizar_exploracion(
                                usuario=st.session_state.usuario,
                                imagen=st.session_state.imagen_preparada,
                                operacion_id=uuid4(),
                            )

                            if res_analisis.ok and res_analisis.valor is not None:
                                st.session_state.exploracion_actual = res_analisis.valor
                                st.session_state.error_analisis = None
                                st.session_state.objeto_seleccionado_id = None
                                # Vincular hash de la imagen para asegurar correspondencia
                                st.session_state.imagen_asociada_id = hash(st.session_state.imagen_preparada.contenido)
                                st.rerun()
                            else:
                                st.session_state.exploracion_actual = None
                                st.session_state.imagen_asociada_id = None
                                st.session_state.error_analisis = (
                                    res_analisis.error.mensaje_usuario
                                    if res_analisis.error
                                    else "Error desconocido al analizar la imagen."
                                )
                                st.rerun()

                elif st.session_state.error_preparacion:
                    st.error(f"❌ {st.session_state.error_preparacion}")
                else:
                    st.info("ℹ️ Presiona **'⚙️ Preparar Imagen'** para validar formato y dimensiones antes del análisis.")

        # Mostrar error persistente de análisis si ocurrió
        if st.session_state.get("error_analisis"):
            st.error(f"❌ Error al analizar la fotografía: {st.session_state.error_analisis}")

        # Renderizar la Exploración Visual (M4) de forma persistente fuera del bloque del botón
        if st.session_state.get("exploracion_actual") is not None:
            # Comprobar correspondencia estricta con la imagen activa
            imagen_valida: ImagenPreparada | None = None
            if (
                st.session_state.imagen_preparada is not None
                and st.session_state.get("imagen_asociada_id") == hash(st.session_state.imagen_preparada.contenido)
            ):
                imagen_valida = st.session_state.imagen_preparada

            mostrar_exploracion(
                exploracion=st.session_state.exploracion_actual,
                imagen=imagen_valida,
            )

    else:
        st.divider()
        st.info("👆 Selecciona un archivo o toma una fotografía con tu cámara para comenzar.")
