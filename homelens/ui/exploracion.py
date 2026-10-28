"""Componente de interfaz para la Exploración Visual y Tarjetas Educativas (M4).

Presenta la fotografía con recuadros delimitadores calculados, etiquetas visibles
y tarjetas pedagógicas asociadas inequívocamente a cada objeto reconocido.
"""

from __future__ import annotations
import html
from typing import Optional
from uuid import UUID
import streamlit as st
import streamlit.components.v1 as components

from homelens.modelos import Exploracion, ImagenPreparada, EstadoAnalisis
from homelens.exploracion import dibujar_recuadros, PALETA_COLORES_OBJETOS
from homelens.ui.estado import descartar_imagen_actual


def _cb_enfocar_objeto_tarjeta(
    objeto_id: Optional[UUID],
    opcion_widget: str,
    key_widget: str,
) -> None:
    """Callback invocado al pulsar un botón de tarjeta (Enfocar o Ver todos)."""
    st.session_state.objeto_seleccionado_id = objeto_id
    st.session_state[key_widget] = opcion_widget
    st.session_state.scroll_hacia_foto = True


def _cb_cambio_selector_superior(
    key_widget: str,
    mapa_opcion_a_id: dict[str, Optional[UUID]],
) -> None:
    """Callback invocado al cambiar manualmente la opción del selector superior."""
    opcion_elegida = st.session_state.get(key_widget)
    id_elegido = mapa_opcion_a_id.get(opcion_elegida)
    st.session_state.objeto_seleccionado_id = id_elegido
    st.session_state.scroll_hacia_foto = True


def mostrar_exploracion(
    exploracion: Exploracion,
    imagen: Optional[ImagenPreparada] = None,
) -> None:
    """Renderiza la pantalla de exploración visual, recuadros y tarjetas pedagógicas.

    Reglas de interfaz:
    1. Si no hay objetos claros o se recomienda repetir captura, muestra mensajes
       pedagógicos claros en español y permite cargar otra fotografía.
    2. Si la fotografía ya no está disponible en memoria temporal, informa la
       situación y muestra las tarjetas educativas de texto sin intentar dibujar
       recuadros sobre otra imagen.
    3. Cuando la fotografía está activa, dibuja recuadros con coordenadas proporcionales
       y etiquetas legibles identificadas numéricamente (#1, #2...).
    4. Permite enfocar un objeto específico destacando su recuadro y su tarjeta,
       o mostrar todos los objetos simultáneamente.
    5. Muestra exclusivamente el contenido educativo (palabra, traducción, frase y
       ejemplo) sin tecnicismos, UUIDs, coordenadas ni detalles del proveedor.
    6. Las interacciones táctiles de selección no realizan nuevas llamadas a Gemini.

    Args:
        exploracion: Exploración validada con objetos detectados.
        imagen: ImagenPreparada activa en memoria o None si ya expiró.
    """
    if exploracion is None:
        return

    # 1. Gestión de estados no utilizables según el análisis
    if exploracion.estado == EstadoAnalisis.SIN_OBJETOS_CLAROS:
        st.warning("🔍 **Sin objetos cotidianos claros identificados**")
        st.markdown(
            """
            No pudimos identificar con suficiente claridad objetos cotidianos en esta fotografía
            para generar tarjetas de vocabulario.
            
            **Consejos para mejorar el resultado:**
            - Asegúrate de que los objetos principales estén bien iluminados.
            - Evita encuadres con demasiado movimiento o desenfoque.
            - Enfoca elementos comunes de tu hogar (taza, mesa, silla, libro, lámpara, etc.).
            """
        )
        if st.button("🔄 Probar con otra fotografía", type="primary", use_container_width=True):
            descartar_imagen_actual()
            st.rerun()
        return

    if exploracion.estado == EstadoAnalisis.REPETIR_CAPTURA:
        st.warning("📸 **Recomendación: Tomar una nueva captura**")
        st.markdown(
            """
            La imagen enviada no cuenta con la nitidez o el encuadre adecuado para el aprendizaje.
            Te recomendamos capturar una nueva fotografía con mejor iluminación.
            """
        )
        if st.button("🔄 Tomar nueva fotografía", type="primary", use_container_width=True):
            descartar_imagen_actual()
            st.rerun()
        return

    # 2. Caso: Exploración utilizable pero sin objetos
    if not exploracion.objetos:
        st.info("ℹ️ No hay objetos registrados para mostrar en esta exploración.")
        return

    st.divider()
    st.header("🔍 Exploración Visual y Vocabulario")
    st.caption("Objetos identificados en tu entorno para aprender inglés:")

    # 3. Control de selección táctil entre objetos
    opciones_seleccion = ["👁️ Ver todos"] + [
        f"#{i + 1} — {obj.nombre_en} / {obj.nombre_es}"
        for i, obj in enumerate(exploracion.objetos)
    ]

    mapa_opcion_a_id: dict[str, Optional[UUID]] = {"👁️ Ver todos": None}
    mapa_id_a_opcion: dict[str, str] = {str(None): "👁️ Ver todos"}
    for i, obj in enumerate(exploracion.objetos):
        etiqueta = f"#{i + 1} — {obj.nombre_en} / {obj.nombre_es}"
        mapa_opcion_a_id[etiqueta] = obj.objeto_id
        mapa_id_a_opcion[str(obj.objeto_id)] = etiqueta

    key_widget = f"selector_objeto_activo_{exploracion.exploracion_id}"
    id_actual = st.session_state.get("objeto_seleccionado_id")
    opcion_sincronizada = mapa_id_a_opcion.get(str(id_actual), "👁️ Ver todos")

    # Inicializar la clave del widget únicamente si aún no existe en session_state
    if key_widget not in st.session_state:
        st.session_state[key_widget] = opcion_sincronizada

    st.markdown("#### Selección de objeto:")
    if hasattr(st, "segmented_control"):
        st.segmented_control(
            "Selecciona un objeto para enfocarlo:",
            options=opciones_seleccion,
            key=key_widget,
            on_change=_cb_cambio_selector_superior,
            args=(key_widget, mapa_opcion_a_id),
            label_visibility="collapsed",
        )
    elif hasattr(st, "pills"):
        st.pills(
            "Selecciona un objeto para enfocarlo:",
            options=opciones_seleccion,
            key=key_widget,
            on_change=_cb_cambio_selector_superior,
            args=(key_widget, mapa_opcion_a_id),
            label_visibility="collapsed",
        )
    else:
        st.radio(
            "Selecciona un objeto para enfocarlo:",
            options=opciones_seleccion,
            key=key_widget,
            horizontal=True,
            on_change=_cb_cambio_selector_superior,
            args=(key_widget, mapa_opcion_a_id),
            label_visibility="collapsed",
        )

    objeto_enfocado_id = st.session_state.get("objeto_seleccionado_id")

    # 4. Renderizado de la fotografía con recuadros
    st.markdown('<div id="visor-fotografia"></div>', unsafe_allow_html=True)

    # Si se solicitó desplazamiento al enfocar, activar scroll suave hacia la imagen
    if st.session_state.get("scroll_hacia_foto"):
        st.session_state.scroll_hacia_foto = False
        components.html(
            """
            <script>
                setTimeout(function() {
                    const doc = window.parent.document;
                    const target = doc.getElementById("visor-fotografia");
                    if (target) {
                        target.scrollIntoView({behavior: "smooth", block: "start"});
                    }
                }, 100);
            </script>
            """,
            height=0,
            width=0,
        )

    # Cartel informativo del objeto actualmente enfocado sobre la fotografía
    if objeto_enfocado_id is not None:
        info_enfocado = next(
            ((i + 1, o) for i, o in enumerate(exploracion.objetos) if str(o.objeto_id) == str(objeto_enfocado_id)),
            None,
        )
        if info_enfocado:
            num_f, obj_f = info_enfocado
            st.success(f"🎯 **Objeto seleccionado: #{num_f} — {obj_f.nombre_en} / {obj_f.nombre_es}**")
        else:
            st.info("👁️ Mostrando todos los objetos reconocidos en la fotografía.")
    else:
        st.info("👁️ Mostrando todos los objetos reconocidos en la fotografía. Haz clic en **'Enfocar'** para aislar un objeto.")

    if imagen is not None and imagen.contenido:
        bytes_anotados = dibujar_recuadros(
            imagen=imagen,
            objetos=exploracion.objetos,
            objeto_seleccionado_id=objeto_enfocado_id,
        )

        subtitulo_foto = (
            "Mostrando todos los objetos reconocidos"
            if objeto_enfocado_id is None
            else "Objeto seleccionado destacado con foco exclusivo"
        )
        st.image(
            bytes_anotados,
            caption=f"Fotografía activa — {subtitulo_foto}",
            use_container_width=True,
        )
    else:
        st.info(
            "ℹ️ **Fotografía temporal no disponible:** La imagen original ya no reside en "
            "la memoria temporal de la sesión. A continuación puedes consultar el vocabulario y "
            "ejemplos generados."
        )

    # 5. Renderizado de las Tarjetas Educativas
    st.markdown("### 📚 Tarjetas Educativas")
    st.caption("Haz clic en una tarjeta o usa los controles superiores para enfocar cada objeto.")

    for i, obj in enumerate(exploracion.objetos):
        numero = i + 1
        es_activo = (objeto_enfocado_id is not None) and (str(objeto_enfocado_id) == str(obj.objeto_id))
        color_item = PALETA_COLORES_OBJETOS[i % len(PALETA_COLORES_OBJETOS)]
        borde_hex = f"#{color_item['borde'][0]:02x}{color_item['borde'][1]:02x}{color_item['borde'][2]:02x}"

        # Escapado seguro contra inyecciones involuntarias
        nombre_en_esc = html.escape(obj.nombre_en)
        nombre_es_esc = html.escape(obj.nombre_es)
        frase_en_esc = html.escape(obj.frase_en)
        frase_es_esc = html.escape(obj.frase_es)

        with st.container(border=True):
            # Cabecera de la tarjeta con número y distintivo si está seleccionado
            col_titulo, col_accion = st.columns([3, 1])
            with col_titulo:
                badge_enfocado = (
                    f"<span style='background-color: {borde_hex}; color: #0f172a; font-weight: bold; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-bottom: 4px; display: inline-block;'>⭐ OBJETO ENFOCADO</span><br>"
                    if es_activo
                    else ""
                )
                st.markdown(
                    f"<div style='border-left: 5px solid {borde_hex}; padding-left: 10px; margin-bottom: 6px;'>"
                    f"{badge_enfocado}"
                    f"<span style='font-size: 0.85em; color: gray;'>OBJETO #{numero}</span><br>"
                    f"<span style='font-size: 1.35em; font-weight: bold;'>🇬🇧 {nombre_en_esc}</span> "
                    f"<span style='font-size: 1.1em; color: #4B5563;'>/ 🇪🇸 {nombre_es_esc}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            with col_accion:
                if es_activo:
                    st.button(
                        "👁️ Ver todos",
                        key=f"btn_unfocus_{obj.objeto_id}",
                        on_click=_cb_enfocar_objeto_tarjeta,
                        args=(None, "👁️ Ver todos", key_widget),
                        use_container_width=True,
                    )
                    st.markdown(
                        "<a href='#visor-fotografia' style='display: block; text-align: center; font-size: 0.85em; text-decoration: none; padding-top: 4px; color: #0284C7; font-weight: 500;'>⬆️ Ver en foto</a>",
                        unsafe_allow_html=True,
                    )
                else:
                    etiqueta_este_obj = mapa_id_a_opcion.get(str(obj.objeto_id), "👁️ Ver todos")
                    st.button(
                        f"🔍 Enfocar #{numero}",
                        key=f"btn_focus_{obj.objeto_id}",
                        on_click=_cb_enfocar_objeto_tarjeta,
                        args=(obj.objeto_id, etiqueta_este_obj, key_widget),
                        use_container_width=True,
                    )

            # Frase de ejemplo pedagógica y su traducción
            st.markdown(
                f"""
                **💬 Frase de ejemplo:**  
                > *"{frase_en_esc}"*  
                > *"{frase_es_esc}"*
                """
            )
