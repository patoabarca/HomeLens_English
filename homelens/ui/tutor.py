"""Componente de interfaz de Streamlit para la práctica opcional con el Agente Tutor.

Conecta la pantalla de Exploración Visual con la skill de entrada `orquestar-practica`,
mostrando al alumno únicamente la consigna pública, las pistas y las devoluciones,
reutilizando el resaltado de recuadros de HomeLens y exponiendo la traza observable
de decisiones y política para la defensa.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
import streamlit as st

from homelens.agente_tutor.cargador import (
    cargar_ejecutor_skill,
    cargar_politica_tutor,
    obtener_adaptador_gemini_tutor,
)
from homelens.agente_tutor.contratos import EstadoPracticaTutor
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import Exploracion


def _sincronizar_resaltado_foto(
    exploracion: Exploracion,
    objeto_resaltado_id: Optional[str],
) -> None:
    """Sincroniza el objeto resaltado por el tutor con el visor de recuadros de HomeLens.

    Como el panel del tutor se dibuja después del selector superior de objetos
    (`selector_objeto_activo_<id>`), guarda la etiqueta en una clave pendiente
    separada (`_pendiente_selector_objeto_activo_<id>`) para aplicarla una sola
    vez antes de instanciar el selector en la siguiente ejecución.
    """
    key_pendiente = f"_pendiente_selector_objeto_activo_{exploracion.exploracion_id}"
    if not objeto_resaltado_id:
        st.session_state.objeto_seleccionado_id = None
        st.session_state[key_pendiente] = "👁️ Ver todos"
        return

    for idx, obj in enumerate(exploracion.objetos):
        if str(obj.objeto_id) == str(objeto_resaltado_id):
            st.session_state.objeto_seleccionado_id = obj.objeto_id
            st.session_state[key_pendiente] = f"#{idx + 1} — {obj.nombre_en} / {obj.nombre_es}"
            return


def _invocar_orquestador_ui(
    evento: str,
    estado_tutor: EstadoPracticaTutor,
    exploracion: Exploracion,
    respuesta_alumno: Optional[str] = None,
    evento_id: Optional[str] = None,
    adaptador: Optional[AdaptadorGemini] = None,
    policy_override: Optional[Dict[str, Any]] = None,
) -> bool:
    """Ejecuta `orquestar-practica` actualizando el estado en sesión y el resaltado."""
    mod_orq = cargar_ejecutor_skill("orquestar-practica", policy=policy_override)
    adaptador_efectivo = adaptador if adaptador is not None else st.session_state.get("_tutor_adaptador_override")
    if adaptador_efectivo is None and st.session_state.get("_tutor_usar_gemini_config", True):
        candidato = obtener_adaptador_gemini_tutor(
            usuario=st.session_state.get("usuario")
        )
        if candidato is not None and candidato.esta_configurado:
            adaptador_efectivo = candidato

    ev_id = evento_id or str(uuid4())
    res = mod_orq.ejecutar_orquestar_practica(
        evento=evento,
        estado_practica=estado_tutor,
        exploracion=exploracion,
        respuesta_alumno=respuesta_alumno,
        evento_id=ev_id,
        adaptador=adaptador_efectivo,
        policy_override=policy_override or st.session_state.get("_tutor_policy_override"),
    )
    st.session_state.tutor_estado = estado_tutor

    if res.ok and res.valor is not None:
        st.session_state.tutor_ultima_operacion_fallida = None
        _sincronizar_resaltado_foto(exploracion, res.valor.objeto_resaltado_id)
        return True

    # Guardar la operación fallida para permitir reintentar sin duplicar el intento anterior
    st.session_state.tutor_ultima_operacion_fallida = {
        "evento": evento,
        "respuesta_alumno": respuesta_alumno,
        "mensaje_error": res.error.mensaje_usuario if res.error else "Error al ejecutar la skill del tutor.",
    }
    return False


def renderizar_seccion_tutor_en_exploracion(
    exploracion: Exploracion,
    adaptador: Optional[AdaptadorGemini] = None,
) -> None:
    """Renderiza el botón «Practicar con el tutor» y, si está activo, el panel interactivo."""
    if exploracion is None or not exploracion.objetos:
        return

    st.divider()
    exp_id_str = str(exploracion.exploracion_id)
    estado_tutor: Optional[EstadoPracticaTutor] = st.session_state.get("tutor_estado")
    if estado_tutor is not None and estado_tutor.exploracion_id != exp_id_str:
        estado_tutor = None
        st.session_state.tutor_estado = None
        st.session_state.tutor_activo = False

    tutor_activo = bool(st.session_state.get("tutor_activo", False))

    if not tutor_activo:
        col_intro, col_btn = st.columns([3, 1], vertical_alignment="center")
        with col_intro:
            st.markdown("#### 🎓 Práctica Guiada con el Agente Tutor (Opcional)")
            st.caption(
                "Activa al tutor para practicar el vocabulario de esta fotografía con consignas breves, "
                "pistas progresivas y ejercicios de refuerzo."
            )
        with col_btn:
            if st.button(
                "🎓 Practicar con el tutor",
                type="secondary",
                use_container_width=True,
                key="btn_practicar_con_tutor",
            ):
                nuevo_estado = EstadoPracticaTutor(exploracion_id=exp_id_str)
                st.session_state.tutor_activo = True
                _invocar_orquestador_ui(
                    evento="INICIAR_PRACTICA",
                    estado_tutor=nuevo_estado,
                    exploracion=exploracion,
                    adaptador=adaptador,
                )
                st.rerun()
        return

    # Si el tutor fue activado pero aún no se inicializó su estado
    if estado_tutor is None:
        estado_tutor = EstadoPracticaTutor(exploracion_id=exp_id_str)
        _invocar_orquestador_ui(
            evento="INICIAR_PRACTICA",
            estado_tutor=estado_tutor,
            exploracion=exploracion,
            adaptador=adaptador,
        )

    pol = st.session_state.get("_tutor_policy_override") or cargar_politica_tutor()
    limites = pol.get("limits") or {}

    with st.container(border=True):
        col_cab, col_salir = st.columns([3, 1], vertical_alignment="center")
        with col_cab:
            st.markdown("### 🎓 Agente Tutor de Vocabulario")
            st.caption(
                f"Respuestas enviadas: **{estado_tutor.turnos_consumidos}/{limites.get('max_turnos', 5)}** · "
                f"Pistas utilizadas: **{estado_tutor.pistas_totales}/{limites.get('max_pistas_totales', 4)}** · "
                f"Refuerzos: **{estado_tutor.refuerzos_realizados}/{limites.get('max_refuerzos', 2)}**"
            )
        with col_salir:
            if st.button(
                "🔙 Volver a explorar la foto",
                use_container_width=True,
                key="btn_tutor_volver_foto",
            ):
                _invocar_orquestador_ui(
                    evento="CERRAR_PRACTICA",
                    estado_tutor=estado_tutor,
                    exploracion=exploracion,
                    adaptador=adaptador,
                )
                st.session_state.tutor_activo = False
                _sincronizar_resaltado_foto(exploracion, None)
                st.rerun()

        # Mostrar error y opción de reintentar sin duplicar el intento anterior
        op_fallida = st.session_state.get("tutor_ultima_operacion_fallida")
        if estado_tutor.error_actual or op_fallida:
            msg_err = estado_tutor.error_actual or (op_fallida.get("mensaje_error") if op_fallida else "")
            st.warning(f"⚠️ {msg_err}")
            if op_fallida:
                if st.button(
                    "🔄 Reintentar operación",
                    key="btn_tutor_reintentar",
                ):
                    _invocar_orquestador_ui(
                        evento=op_fallida["evento"],
                        estado_tutor=estado_tutor,
                        exploracion=exploracion,
                        respuesta_alumno=op_fallida.get("respuesta_alumno"),
                        adaptador=adaptador,
                    )
                    st.rerun()

        # Mostrar devolución de la última evaluación si existe
        if estado_tutor.ultima_evaluacion is not None:
            ev = estado_tutor.ultima_evaluacion
            if ev.valoracion == "CORRECTA":
                st.success(f"✅ **{ev.devolucion}**")
            elif ev.valoracion == "PARCIAL":
                st.info(f"🟡 **{ev.devolucion}**")
            else:
                st.warning(f"🔎 **{ev.devolucion}**")

            if estado_tutor.mensaje_transicion:
                st.caption(f"🧭 *Decisión del tutor ({estado_tutor.ultima_accion_pedagogica}):* {estado_tutor.mensaje_transicion}")

        # Estado de cierre de la práctica
        if estado_tutor.estado == "FINALIZADA":
            st.info(f"🏁 {estado_tutor.mensaje_cierre or 'Práctica finalizada.'}")
            if st.button(
                "🔄 Iniciar nueva ronda con el tutor",
                type="primary",
                key="btn_tutor_reiniciar",
            ):
                _invocar_orquestador_ui(
                    evento="INICIAR_PRACTICA",
                    estado_tutor=estado_tutor,
                    exploracion=exploracion,
                    adaptador=adaptador,
                )
                st.rerun()
        elif estado_tutor.actividad_actual is not None:
            # Mostrar al alumno únicamente la proyección pública vista_alumno()
            vista_publica = estado_tutor.actividad_actual.vista_alumno()
            etiqueta_tipo = "🔁 Consigna de refuerzo" if vista_publica["es_refuerzo"] else "📝 Consigna actual"
            st.markdown(
                f"""
                <div style='background-color: rgba(37, 99, 235, 0.07); border-left: 4px solid #2563EB; padding: 12px 16px; border-radius: 8px; margin: 8px 0 12px 0;'>
                    <div style='font-size: 0.82rem; font-weight: 700; color: #1D4ED8; text-transform: uppercase;'>{etiqueta_tipo}</div>
                    <div style='font-size: 1.08rem; font-weight: 600; color: #0F172A; margin-top: 4px;'>{vista_publica["consigna"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Mostrar pistas otorgadas para la actividad vigente
            for pista in estado_tutor.pistas_actividad_actual:
                origen_lbl = "Solicitada por el alumno" if pista.origen == "SOLICITUD_ALUMNO" else "Ofrecida por el tutor"
                st.info(f"💡 **Pista #{pista.numero_pista}** (*{origen_lbl}*): {pista.texto_pista}")

            # Si el alumno acertó y la decisión fue AVANZAR, ofrecer botón para pasar al siguiente objeto
            if estado_tutor.estado == "EVALUADA" and estado_tutor.ultima_accion_pedagogica == "AVANZAR":
                if st.button(
                    "➡️ Siguiente actividad",
                    type="primary",
                    use_container_width=True,
                    key="btn_tutor_avanzar",
                ):
                    _invocar_orquestador_ui(
                        evento="AVANZAR_ACTIVIDAD",
                        estado_tutor=estado_tutor,
                        exploracion=exploracion,
                        adaptador=adaptador,
                    )
                    st.rerun()
            else:
                key_input = (
                    f"input_respuesta_tutor_{vista_publica['actividad_tutor_id']}_"
                    f"{estado_tutor.turnos_consumidos}"
                )
                respuesta_txt = st.text_input(
                    "Escribe tu respuesta en inglés:",
                    key=key_input,
                    placeholder="Ej.: coffee mug, lamp, chair...",
                )
                col_env, col_pista = st.columns(2)
                with col_env:
                    if st.button(
                        "📨 Enviar respuesta",
                        type="primary",
                        use_container_width=True,
                        key="btn_tutor_enviar_respuesta",
                    ):
                        _invocar_orquestador_ui(
                            evento="ENVIAR_RESPUESTA",
                            estado_tutor=estado_tutor,
                            exploracion=exploracion,
                            respuesta_alumno=respuesta_txt,
                            adaptador=adaptador,
                        )
                        st.rerun()
                with col_pista:
                    if st.button(
                        "💡 Dame una pista",
                        use_container_width=True,
                        key="btn_tutor_pedir_pista",
                    ):
                        _invocar_orquestador_ui(
                            evento="PEDIR_PISTA",
                            estado_tutor=estado_tutor,
                            exploracion=exploracion,
                            adaptador=adaptador,
                        )
                        st.rerun()

        # Registro observable de eventos para la defensa
        with st.expander("🔎 Registro observable del Agente Tutor (Defensa)", expanded=False):
            if not estado_tutor.traza_observable:
                st.caption("Aún no se registraron eventos del tutor en esta sesión.")
            else:
                for reg in estado_tutor.traza_observable:
                    icono_pol = "🟢" if reg.decision_politica == "AUTORIZADA" else "🔴"
                    st.markdown(
                        f"**Paso {reg.paso}** · {icono_pol} `{reg.decision_politica}` · "
                        f"Skill: `{reg.skill_ejecutada}` · Evento: `{reg.evento_usuario}`  \n"
                        f"↳ {reg.resumen_observable} "
                        f"*(Respuestas: {reg.conteo_respuestas} · Pistas: {reg.conteo_pistas})*"
                    )
