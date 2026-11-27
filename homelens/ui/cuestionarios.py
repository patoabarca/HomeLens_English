"""Componente de interfaz para Cuestionarios Pedagógicos Interactivos (M6 - Tarea 9 y Parte 10).

Permite al estudiante responder de forma interactiva a las actividades educativas
generadas por Gemini durante la exploración visual, evaluando las respuestas localmente
con retroalimentación pedagógica inmediata, guardando los intentos de forma idempotente
al finalizar el cuestionario y consultando los resultados anteriores para repasar.
"""

from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import html
import streamlit as st

from homelens.config import Configuracion, cargar_configuracion
from homelens.datos.repositorio import RepositorioHomeLens
from homelens.datos.supabase import RepositorioSupabase
from homelens.modelos import (
    ContextoUsuario,
    Exploracion,
    Actividad,
    Opcion,
    IntentoPractica,
    TipoIntento,
    ResultadoIntento,
    ResultadoPractica,
    EstadoAnalisis,
)
from homelens.practicas import (
    construir_intento_cuestionario,
    obtener_actividad_publica,
    mezclar_opciones_actividad,
    validar_y_responder_actividad,
)
from homelens.ui.estado import inicializar_estado_sesion, limpiar_datos_cuestionario

try:
    _TZ_ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")
except ZoneInfoNotFoundError:
    _TZ_ARGENTINA = timezone(timedelta(hours=-3), name="ART")


def _formatear_fecha_intento(fecha: datetime) -> str:
    """Formatea una fecha UTC en hora local de Argentina para repaso."""
    fecha_utc = fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)
    return fecha_utc.astimezone(_TZ_ARGENTINA).strftime("%d/%m/%Y — %H:%M ART")


def _obtener_repositorio_cuestionarios(
    config: Optional[Configuracion] = None,
    repositorio: Optional[RepositorioHomeLens] = None,
) -> RepositorioHomeLens:
    """Construye o reutiliza el repositorio de persistencia respetando aislamiento de sesión."""
    if repositorio is not None:
        return repositorio
    cfg = config
    if cfg is None:
        res_cfg = cargar_configuracion()
        cfg = res_cfg.valor if res_cfg.ok else None
    tiene_sb = bool(cfg and cfg.tiene_supabase)
    return RepositorioSupabase(
        supabase_url=cfg.supabase_url if tiene_sb and cfg else None,
        anon_key=cfg.supabase_anon_key if tiene_sb and cfg else None,
        almacen_demo=st.session_state.get("_exploraciones_demo"),
        almacen_intentos_demo=st.session_state.get("_intentos_demo"),
    )


def guardar_intentos_cuestionario_finalizado(
    usuario: ContextoUsuario,
    actividades: List[Actividad],
    repositorio: RepositorioHomeLens,
) -> bool:
    """Guarda de forma idempotente los intentos del cuestionario finalizado conservando el mismo intento_id.

    Si algún intento falla al guardarse:
    - Conserva los resultados visibles y los intento_id ya generados.
    - Registra el mensaje de error en `cuestionario_error_guardado` para permitir reintentar
      con el mismo ID sin volver a corregir el cuestionario.
    """
    respuestas: dict[UUID, ResultadoPractica] = st.session_state.setdefault("cuestionario_respuestas", {})
    opciones_elegidas: dict[UUID, str] = st.session_state.setdefault("cuestionario_opciones_elegidas", {})
    intentos_map: dict[UUID, IntentoPractica] = st.session_state.setdefault("cuestionario_intentos", {})
    guardados_ids: set[UUID] = st.session_state.setdefault("cuestionario_intentos_guardados_ids", set())

    errores: list[str] = []

    for act in actividades:
        res_prac = respuestas.get(act.actividad_id)
        if res_prac is None:
            continue

        intento = intentos_map.get(act.actividad_id)
        if intento is None:
            opc_id = opciones_elegidas.get(act.actividad_id, "")
            intento = construir_intento_cuestionario(
                usuario=usuario,
                actividad=act,
                opcion_elegida_id=opc_id,
                resultado_practica=res_prac,
            )
            intentos_map[act.actividad_id] = intento

        if intento.intento_id in guardados_ids and res_prac.registrado:
            continue

        res_guardado = repositorio.guardar_intento(usuario, intento)
        if res_guardado.ok:
            guardados_ids.add(intento.intento_id)
            respuestas[act.actividad_id] = replace(res_prac, registrado=True)
        else:
            msg = (
                res_guardado.error.mensaje_usuario
                if res_guardado.error
                else "No fue posible guardar el resultado del cuestionario."
            )
            errores.append(msg)

    st.session_state.cuestionario_guardado_intentado = True
    if errores:
        st.session_state.cuestionario_error_guardado = errores[0]
        return False

    st.session_state.cuestionario_error_guardado = None
    return True


def _renderizar_repaso_intentos_cuestionario(
    usuario: ContextoUsuario,
    repositorio: RepositorioHomeLens,
    exploracion_actual: Optional[Exploracion] = None,
) -> None:
    """Consulta y presenta los resultados de cuestionarios anteriores del usuario para repasar."""
    st.divider()
    st.subheader("📚 Repaso de Resultados Anteriores (Cuestionarios)")
    st.caption("Consulta tus respuestas previas ordenadas de la más reciente a la más antigua.")

    res_intentos = repositorio.listar_intentos(usuario)
    if not res_intentos.ok:
        st.warning(
            f"⚠️ {res_intentos.error.mensaje_usuario if res_intentos.error else 'No se pudieron recuperar tus intentos anteriores.'}"
        )
        return

    todos_intentos = res_intentos.valor or []
    intentos_cuestionario = [
        it for it in todos_intentos if it.tipo == TipoIntento.CUESTIONARIO
    ]

    if not intentos_cuestionario:
        st.info("ℹ️ Aún no tienes intentos de cuestionarios guardados para repasar.")
        return

    # Construir índice de actividades y objetos conocidos (exploración activa + exploraciones del usuario)
    mapa_actividades: Dict[UUID, Actividad] = {}
    mapa_objetos: Dict[UUID, str] = {}

    if exploracion_actual is not None:
        for obj in exploracion_actual.objetos:
            mapa_objetos[obj.objeto_id] = f"{obj.nombre_en} ({obj.nombre_es})"
        for act in exploracion_actual.actividades:
            mapa_actividades[act.actividad_id] = act

    res_vocab = repositorio.listar_vocabulario(usuario)
    if res_vocab.ok and res_vocab.valor:
        for obj in res_vocab.valor:
            if obj.objeto_id not in mapa_objetos:
                mapa_objetos[obj.objeto_id] = f"{obj.nombre_en} ({obj.nombre_es})"

    with st.expander(
        f"📖 Ver historial de intentos de cuestionarios ({len(intentos_cuestionario)})",
        expanded=True,
    ):
        for it in intentos_cuestionario:
            es_correcto = it.resultado == ResultadoIntento.CORRECTO
            icono = "✅" if es_correcto else "❌"
            etiqueta_res = "Correcto" if es_correcto else "Incorrecto"
            fecha_str = _formatear_fecha_intento(it.fecha)

            act_conocida = mapa_actividades.get(it.actividad_id) if it.actividad_id else None
            nombres_obj = [
                mapa_objetos[oid] for oid in it.objeto_ids if oid in mapa_objetos
            ]
            vocab_str = ", ".join(nombres_obj) if nombres_obj else "Vocabulario practicado"

            with st.container(border=True):
                st.markdown(f"{icono} **{etiqueta_res}** · 📅 `{fecha_str}`")
                if act_conocida is not None:
                    st.markdown(f"**Pregunta:** {act_conocida.pregunta}")
                    if it.opcion_elegida_id:
                        txt_opc = next(
                            (o.texto for o in act_conocida.opciones if o.opcion_id == it.opcion_elegida_id),
                            it.opcion_elegida_id,
                        )
                        st.caption(f"Opción elegida: {txt_opc} · Objetos: {vocab_str}")
                else:
                    detalles = [f"Objetos: {vocab_str}"]
                    if it.opcion_elegida_id:
                        detalles.append(f"Opción elegida: {it.opcion_elegida_id}")
                    st.caption(" · ".join(detalles))


def renderizar_pantalla_cuestionarios(
    config: Optional[Configuracion] = None,
    repositorio: Optional[RepositorioHomeLens] = None,
) -> None:
    """Renderiza la experiencia completa de cuestionarios interactivos y el repaso de intentos."""
    inicializar_estado_sesion()

    st.header("📝 Prácticas y Cuestionarios")
    st.caption("Responde preguntas contextualizadas sobre los objetos cotidianos de tu hogar.")

    usuario: Optional[ContextoUsuario] = st.session_state.get("usuario")
    if usuario is None:
        st.warning("🔒 Debes iniciar sesión con tu cuenta para acceder a los cuestionarios.")
        return

    repo = _obtener_repositorio_cuestionarios(config=config, repositorio=repositorio)
    exploracion: Optional[Exploracion] = st.session_state.get("exploracion_actual")

    # 1. Caso: Sin exploración activa -> Mostrar aviso y permitir repasar intentos guardados
    if exploracion is None:
        st.info(
            "ℹ️ **Aún no has explorado ninguna fotografía en esta sesión.**\n\n"
            "Toma o sube una fotografía en la sección **Exploración Visual** y analízala con IA "
            "para generar cuestionarios personalizados basados en los objetos de tu entorno."
        )
        if st.button("📸 Ir a Exploración Visual", type="primary", use_container_width=True):
            st.session_state.seccion_navegacion = "Exploración Visual"
            st.rerun()

        _renderizar_repaso_intentos_cuestionario(usuario=usuario, repositorio=repo, exploracion_actual=None)
        return

    # 2. Caso: Exploración en estados no utilizables
    if exploracion.estado in (
        EstadoAnalisis.SIN_OBJETOS_CLAROS,
        EstadoAnalisis.REPETIR_CAPTURA,
        EstadoAnalisis.FUERA_DE_ALCANCE,
    ):
        st.warning("🔍 **No hay actividades para esta fotografía.**")
        st.markdown(
            "La fotografía analizada no cuenta con objetos cotidianos suficientemente claros "
            "para generar un cuestionario pedagógico. Te sugerimos capturar una nueva foto."
        )
        if st.button("🔄 Ir a capturar otra fotografía", type="primary", use_container_width=True):
            st.session_state.seccion_navegacion = "Exploración Visual"
            st.rerun()

        _renderizar_repaso_intentos_cuestionario(usuario=usuario, repositorio=repo, exploracion_actual=exploracion)
        return

    # 3. Caso: Sin actividades generadas
    actividades = exploracion.actividades or []
    if not actividades:
        st.warning("⚠️ **Esta exploración no contiene actividades educativas.**")
        st.markdown("Intenta capturar una escena con elementos cotidianos (tazas, libros, mesas, sillas, etc.).")
        if st.button("📸 Volver a Exploración Visual", use_container_width=True):
            st.session_state.seccion_navegacion = "Exploración Visual"
            st.rerun()

        _renderizar_repaso_intentos_cuestionario(usuario=usuario, repositorio=repo, exploracion_actual=exploracion)
        return

    # 4. Asegurar correspondencia estricta con la exploración activa
    if st.session_state.get("cuestionario_exploracion_id") != exploracion.exploracion_id:
        limpiar_datos_cuestionario()
        st.session_state.cuestionario_exploracion_id = exploracion.exploracion_id

    total_actividades = len(actividades)

    # 5. Vista de Resumen Final (cuando el cuestionario fue completado)
    if st.session_state.get("cuestionario_finalizado", False):
        _renderizar_resumen_final(
            usuario=usuario,
            exploracion=exploracion,
            actividades=actividades,
            total=total_actividades,
            repositorio=repo,
        )
        return

    # 6. Vista de Pregunta Individual
    indice = st.session_state.get("cuestionario_indice_actual", 0)
    if indice >= total_actividades:
        st.session_state.cuestionario_finalizado = True
        guardar_intentos_cuestionario_finalizado(usuario, actividades, repo)
        st.rerun()
        return

    actividad_actual = actividades[indice]
    _renderizar_actividad_individual(
        usuario=usuario,
        actividad=actividad_actual,
        actividades=actividades,
        indice=indice,
        total=total_actividades,
        repositorio=repo,
    )

    _renderizar_repaso_intentos_cuestionario(
        usuario=usuario,
        repositorio=repo,
        exploracion_actual=exploracion,
    )


def _renderizar_actividad_individual(
    usuario: ContextoUsuario,
    actividad: Actividad,
    actividades: List[Actividad],
    indice: int,
    total: int,
    repositorio: RepositorioHomeLens,
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
                    # Guardar respuesta, opción elegida e IntentoPractica con su intento_id único
                    st.session_state.cuestionario_respuestas[actividad.actividad_id] = res_evaluacion.valor
                    st.session_state.cuestionario_opciones_elegidas[actividad.actividad_id] = id_opcion_seleccionada
                    intentos_map: dict[UUID, IntentoPractica] = st.session_state.setdefault("cuestionario_intentos", {})
                    intentos_map[actividad.actividad_id] = construir_intento_cuestionario(
                        usuario=usuario,
                        actividad=actividad,
                        opcion_elegida_id=id_opcion_seleccionada,
                        resultado_practica=res_evaluacion.valor,
                    )
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
                    guardar_intentos_cuestionario_finalizado(usuario, actividades, repositorio)
                else:
                    st.session_state.cuestionario_indice_actual = indice + 1
                    st.session_state.cuestionario_confirmado = False
                st.rerun()


def _renderizar_resumen_final(
    usuario: ContextoUsuario,
    exploracion: Exploracion,
    actividades: list[Actividad],
    total: int,
    repositorio: RepositorioHomeLens,
) -> None:
    """Muestra el reporte pedagógico final, el estado del guardado y el repaso de resultados."""
    # Si se llegó al resumen final sin haber intentado aún el guardado automático, ejecutarlo una vez
    if not st.session_state.get("cuestionario_guardado_intentado", False):
        guardar_intentos_cuestionario_finalizado(usuario, actividades, repositorio)

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

    # Estado de persistencia y botón de reintento con el mismo intento_id si falló
    error_guardado = st.session_state.get("cuestionario_error_guardado")
    if error_guardado:
        st.error(f"❌ No se pudo guardar el resultado: {error_guardado}")
        if st.button(
            "💾 Reintentar guardado de resultados",
            type="primary",
            use_container_width=True,
            key="btn_reintentar_guardado_cuestionario",
        ):
            if guardar_intentos_cuestionario_finalizado(usuario, actividades, repositorio):
                st.toast("✅ Resultados guardados correctamente.")
            st.rerun()
    else:
        todos_registrados = bool(respuestas) and all(r.registrado for r in respuestas.values())
        if todos_registrados:
            st.success("💾 Tus resultados de este cuestionario fueron guardados para repasar.")

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

    # Acciones posteriores (un intento nuevo iniciado por el usuario genera nuevos intento_id)
    col_reiniciar, col_volver = st.columns(2)
    with col_reiniciar:
        if st.button("🔄 Reiniciar este cuestionario", use_container_width=True, key="btn_reiniciar_cuestionario"):
            limpiar_datos_cuestionario()
            if st.session_state.get("exploracion_actual") is not None:
                st.session_state.cuestionario_exploracion_id = st.session_state.exploracion_actual.exploracion_id
            st.rerun()

    with col_volver:
        if st.button("📸 Volver a la Exploración Visual", type="primary", use_container_width=True, key="btn_volver_exploracion_cuestionario"):
            st.session_state.seccion_navegacion = "Exploración Visual"
            st.rerun()

    _renderizar_repaso_intentos_cuestionario(
        usuario=usuario,
        repositorio=repositorio,
        exploracion_actual=exploracion,
    )
