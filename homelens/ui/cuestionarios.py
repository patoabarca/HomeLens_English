"""Componente de interfaz para Cuestionarios Pedagógicos Interactivos (M6 - Tarea 9).

Permite al estudiante responder de forma interactiva a las actividades educativas
generadas por Gemini durante la exploración visual, evaluando las respuestas localmente
con retroalimentación pedagógica inmediata y navegación pregunta a pregunta,
sin realizar nuevas llamadas a modelos externos ni persistencia en base de datos.
"""

from __future__ import annotations
from typing import Optional
from uuid import UUID, uuid4
import html
import streamlit as st

from homelens.modelos import (
    ContextoUsuario,
    Exploracion,
    Actividad,
    Opcion,
    ResultadoIntento,
    ResultadoPractica,
    EstadoAnalisis,
)
from homelens.practicas import (
    obtener_actividad_publica,
    mezclar_opciones_actividad,
    validar_y_responder_actividad,
)
from homelens.ui.estado import limpiar_datos_cuestionario


def renderizar_pantalla_cuestionarios() -> None:
    """Renderiza la experiencia completa de cuestionarios interactivos.

    Diseñada con enfoque mobile-first y adaptable a notebooks, respetando modo
    claro y oscuro con componentes semánticos de Streamlit.
    """
    st.header("📝 Prácticas y Cuestionarios")
    st.caption("Responde preguntas contextualizadas sobre los objetos cotidianos de tu hogar.")

    usuario: Optional[ContextoUsuario] = st.session_state.get("usuario")
    if usuario is None:
        st.warning("🔒 Debes iniciar sesión con tu cuenta para acceder a los cuestionarios.")
        return

    exploracion: Optional[Exploracion] = st.session_state.get("exploracion_actual")

    # 1. Caso: Sin exploración activa
    if exploracion is None:
        st.info(
            "ℹ️ **Aún no has explorado ninguna fotografía.**\n\n"
            "Toma o sube una fotografía en la sección **Exploración Visual** y analízala con IA "
            "para generar cuestionarios personalizados basados en los objetos de tu entorno."
        )
        if st.button("📸 Ir a Exploración Visual", type="primary", use_container_width=True):
            st.session_state.seccion_navegacion = "Exploración Visual"
            st.rerun()
        return

    # 2. Caso: Exploración en estados no utilizables
    if exploracion.estado in (EstadoAnalisis.SIN_OBJETOS_CLAROS, EstadoAnalisis.REPETIR_CAPTURA):
        st.warning("🔍 **No hay actividades para esta fotografía.**")
        st.markdown(
            "La fotografía analizada no cuenta con objetos cotidianos suficientemente claros "
            "para generar un cuestionario pedagógico. Te sugerimos capturar una nueva foto."
        )
        if st.button("🔄 Ir a capturar otra fotografía", type="primary", use_container_width=True):
            st.session_state.seccion_navegacion = "Exploración Visual"
            st.rerun()
        return

    # 3. Caso: Sin actividades generadas
    actividades = exploracion.actividades or []
    if not actividades:
        st.warning("⚠️ **Esta exploración no contiene actividades educativas.**")
        st.markdown("Intenta capturar una escena con elementos cotidianos (tazas, libros, mesas, sillas, etc.).")
        if st.button("📸 Volver a Exploración Visual", use_container_width=True):
            st.session_state.seccion_navegacion = "Exploración Visual"
            st.rerun()
        return

    # 4. Asegurar correspondencia estricta con la exploración activa
    if st.session_state.get("cuestionario_exploracion_id") != exploracion.exploracion_id:
        limpiar_datos_cuestionario()
        st.session_state.cuestionario_exploracion_id = exploracion.exploracion_id

    total_actividades = len(actividades)

    # 5. Vista de Resumen Final (cuando el cuestionario fue completado)
    if st.session_state.get("cuestionario_finalizado", False):
        _renderizar_resumen_final(actividades, total_actividades)
        return

    # 6. Vista de Pregunta Individual
    indice = st.session_state.get("cuestionario_indice_actual", 0)
    if indice >= total_actividades:
        st.session_state.cuestionario_finalizado = True
        st.rerun()
        return

    actividad_actual = actividades[indice]
    _renderizar_actividad_individual(
        usuario=usuario,
        actividad=actividad_actual,
        indice=indice,
        total=total_actividades,
    )


def _renderizar_actividad_individual(
    usuario: ContextoUsuario,
    actividad: Actividad,
    indice: int,
    total: int,
) -> None:
    """Muestra una única actividad interactiva con sus opciones y feedback pedagógico."""
    actividad_pub = obtener_actividad_publica(actividad)

    # Indicador de progreso superior
    progreso_val = (indice + 1) / total
    st.progress(progreso_val)

    col_progreso, col_nav = st.columns([2, 1])
    with col_progreso:
        st.caption(f"Pregunta **{indice + 1}** de **{total}**")
    with col_nav:
        if st.button("📸 Ver exploración", key=f"btn_ir_exploracion_{actividad.actividad_id}", use_container_width=True):
            st.session_state.seccion_navegacion = "Exploración Visual"
            st.rerun()

    # Contenedor visual de la pregunta (estilo tarjeta clara y accesible)
    st.markdown(
        f"""
        <div style='background-color: rgba(2, 132, 199, 0.08); border-left: 5px solid #0284c7; padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;'>
            <span style='font-size: 0.85em; font-weight: bold; color: #0284c7; text-transform: uppercase;'>Actividad Práctica #{indice + 1}</span>
            <h3 style='margin: 8px 0 0 0; font-size: 1.25em;'>❓ {html.escape(actividad_pub.pregunta)}</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Comprobar si esta actividad ya fue confirmada previamente en esta sesión
    respuestas: dict[UUID, ResultadoPractica] = st.session_state.get("cuestionario_respuestas", {})
    opciones_elegidas: dict[UUID, str] = st.session_state.get("cuestionario_opciones_elegidas", {})
    resultado_previo = respuestas.get(actividad.actividad_id)
    ha_sido_confirmada = resultado_previo is not None

    # Orden mezclado estable para esta actividad durante el intento actual
    ordenes_opciones: dict[UUID, list[Opcion]] = st.session_state.setdefault("cuestionario_orden_opciones", {})
    if actividad.actividad_id not in ordenes_opciones:
        ordenes_opciones[actividad.actividad_id] = mezclar_opciones_actividad(actividad)

    opciones_visibles = ordenes_opciones[actividad.actividad_id]

    # Mapeo de opciones visibles con letras A, B, C asignadas según el nuevo orden visible
    letras = ["A", "B", "C"]
    mapa_etiqueta_a_id: dict[str, str] = {}
    mapa_id_a_etiqueta: dict[str, str] = {}
    lista_etiquetas: list[str] = []

    for i, opc in enumerate(opciones_visibles):
        letra = letras[i] if i < len(letras) else str(i + 1)
        etiqueta = f"{letra}) {opc.texto}"
        mapa_etiqueta_a_id[etiqueta] = opc.opcion_id
        mapa_id_a_etiqueta[opc.opcion_id] = etiqueta
        lista_etiquetas.append(etiqueta)

    # Determinar índice para st.radio:
    # Si la actividad aún no fue confirmada, index=None (ninguna preseleccionada)
    # Si ya fue confirmada, index apunta a la opción elegida por el usuario y se deshabilita
    index_seleccion: Optional[int] = None
    if ha_sido_confirmada:
        opcion_guardada = opciones_elegidas.get(actividad.actividad_id)
        if opcion_guardada and opcion_guardada in mapa_id_a_etiqueta:
            etiqueta_guardada = mapa_id_a_etiqueta[opcion_guardada]
            if etiqueta_guardada in lista_etiquetas:
                index_seleccion = lista_etiquetas.index(etiqueta_guardada)

    # Selector de opciones de respuesta
    st.markdown("**Selecciona tu respuesta:**")
    etiqueta_seleccionada = st.radio(
        label=f"Opciones para la actividad {indice + 1}",
        options=lista_etiquetas,
        index=index_seleccion,
        key=f"radio_actividad_{actividad.actividad_id}",
        disabled=ha_sido_confirmada,
        label_visibility="collapsed",
    )

    id_opcion_seleccionada = mapa_etiqueta_a_id.get(etiqueta_seleccionada, "") if etiqueta_seleccionada else ""

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # 1. Caso: Todavía no ha confirmado su respuesta
    if not ha_sido_confirmada:
        col_btn, _ = st.columns([1, 1])
        with col_btn:
            if st.button("✅ Confirmar respuesta", type="primary", use_container_width=True, key=f"btn_confirmar_{actividad.actividad_id}"):
                # Validar que el usuario haya seleccionado efectivamente una opción
                if not etiqueta_seleccionada or not id_opcion_seleccionada:
                    st.warning("⚠️ Debes seleccionar una de las tres opciones antes de confirmar tu respuesta.")
                    return

                # Doble verificación contra respuestas duplicadas
                if actividad.actividad_id in st.session_state.cuestionario_respuestas:
                    st.rerun()
                    return

                res_evaluacion = validar_y_responder_actividad(
                    usuario=usuario,
                    actividad=actividad,
                    opcion_id=id_opcion_seleccionada,
                    intento_id=uuid4(),
                )

                if res_evaluacion.ok and res_evaluacion.valor is not None:
                    # Guardar respuesta e identificador de opción elegida
                    st.session_state.cuestionario_respuestas[actividad.actividad_id] = res_evaluacion.valor
                    st.session_state.cuestionario_opciones_elegidas[actividad.actividad_id] = id_opcion_seleccionada
                    st.session_state.cuestionario_confirmado = True
                    st.rerun()
                else:
                    mensaje_error = (
                        res_evaluacion.error.mensaje_usuario
                        if res_evaluacion.error
                        else "No fue posible evaluar tu respuesta."
                    )
                    st.error(f"❌ {mensaje_error}")

    # 2. Caso: Respuesta confirmada -> Mostrar devolución didáctica inmediata
    else:
        es_acierto = (resultado_previo.resultado == ResultadoIntento.CORRECTO)

        if es_acierto:
            st.success("🎉 **¡Excelente! Tu respuesta es correcta.**")
        else:
            # Buscar texto didáctico de la opción correcta almacenada en el servidor
            texto_correcta = next(
                (o.texto for o in actividad.opciones if o.opcion_id == actividad.opcion_correcta_id),
                actividad.opcion_correcta_id,
            )
            st.error(f"❌ **Respuesta incorrecta.** La opción correcta era: **{texto_correcta}**")

        # Explicación educativa recibida del servidor
        st.info(f"💡 **Explicación pedagógica:**\n\n{resultado_previo.explicacion}")

        st.divider()

        # Botón de avance
        col_next, _ = st.columns([1, 1])
        with col_next:
            es_ultima = (indice + 1 >= total)
            etiqueta_boton_siguiente = "🎉 Ver resumen final" if es_ultima else "Siguiente actividad ➡️"

            if st.button(etiqueta_boton_siguiente, type="primary", use_container_width=True, key=f"btn_sig_{actividad.actividad_id}"):
                if es_ultima:
                    st.session_state.cuestionario_finalizado = True
                else:
                    st.session_state.cuestionario_indice_actual = indice + 1
                    st.session_state.cuestionario_confirmado = False
                st.rerun()


def _renderizar_resumen_final(actividades: list[Actividad], total: int) -> None:
    """Muestra el reporte pedagógico final con el puntaje y desglose educativo."""
    respuestas: dict[UUID, ResultadoPractica] = st.session_state.get("cuestionario_respuestas", {})
    opciones_elegidas: dict[UUID, str] = st.session_state.get("cuestionario_opciones_elegidas", {})

    total_correctas = sum(
        1 for r in respuestas.values() if r.resultado == ResultadoIntento.CORRECTO
    )

    porcentaje = int(round((total_correctas / total) * 100)) if total > 0 else 0

    st.balloons() if total_correctas == total else None

    # Tarjeta de resumen general
    color_borde = "#16a34a" if total_correctas == total else ("#0284c7" if total_correctas > 0 else "#ea580c")
    st.markdown(
        f"""
        <div style='background-color: rgba(22, 163, 74, 0.05); border: 2px solid {color_borde}; padding: 24px; border-radius: 12px; text-align: center; margin-bottom: 24px;'>
            <h2 style='margin: 0 0 10px 0;'>🏁 ¡Cuestionario Completado!</h2>
            <p style='font-size: 1.15em; color: #4B5563; margin-bottom: 12px;'>Has respondido todas las actividades de esta exploración.</p>
            <div style='font-size: 2.5em; font-weight: bold; color: {color_borde}; margin-bottom: 8px;'>
                {total_correctas} / {total}
            </div>
            <p style='font-weight: 500; font-size: 1.1em;'>Rendimiento: <strong>{porcentaje}% de aciertos</strong></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Detalle de cada pregunta
    st.subheader("📋 Revisión de Respuestas")
    for i, act in enumerate(actividades):
        resultado = respuestas.get(act.actividad_id)
        if resultado is None:
            continue

        acerto = (resultado.resultado == ResultadoIntento.CORRECTO)
        icono = "✅" if acerto else "❌"
        titulo_expander = f"{icono} Actividad {i + 1}: {act.pregunta}"

        with st.expander(titulo_expander, expanded=(not acerto)):
            opc_id_elegida = opciones_elegidas.get(act.actividad_id)
            texto_elegida = next((o.texto for o in act.opciones if o.opcion_id == opc_id_elegida), "No seleccionada")
            texto_correcta = next((o.texto for o in act.opciones if o.opcion_id == act.opcion_correcta_id), "")

            st.write(f"• **Tu respuesta:** {texto_elegida}")
            if not acerto:
                st.write(f"• **Respuesta correcta:** {texto_correcta}")
            st.info(f"💡 **Explicación:** {resultado.explicacion}")

    st.divider()

    # Acciones posteriores
    col_reiniciar, col_volver = st.columns(2)
    with col_reiniciar:
        if st.button("🔄 Reiniciar este cuestionario", use_container_width=True):
            limpiar_datos_cuestionario()
            if st.session_state.get("exploracion_actual") is not None:
                st.session_state.cuestionario_exploracion_id = st.session_state.exploracion_actual.exploracion_id
            st.rerun()

    with col_volver:
        if st.button("📸 Volver a la Exploración Visual", type="primary", use_container_width=True):
            st.session_state.seccion_navegacion = "Exploración Visual"
            st.rerun()
