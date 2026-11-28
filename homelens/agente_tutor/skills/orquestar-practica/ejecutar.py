"""Ejecutor real de la skill orquestar-practica (punto de entrada del Agente Tutor)."""

from __future__ import annotations
from typing import Any, Dict, Literal, Optional

from homelens.agente_tutor.cargador import (
    cargar_ejecutor_skill,
    cargar_politica_tutor,
    validar_ids_pertenecen_a_foto,
)
from homelens.agente_tutor.contratos import (
    EstadoPracticaTutor,
    EsquemaDecisionOrquestadorIA,
    EvaluacionTutor,
)
from homelens.errores import (
    CODIGO_ACCESO_DENEGADO,
    CODIGO_LIMITE_ALCANZADO,
    CODIGO_RESPUESTA_INVALIDA,
    Resultado,
)
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import Exploracion, ObjetoEducativo


def _obtener_objeto_por_id(
    exploracion: Exploracion,
    objeto_id: str,
) -> Optional[ObjetoEducativo]:
    for obj in exploracion.objetos:
        if str(obj.objeto_id) == str(objeto_id):
            return obj
    return None


def _decidir_accion_pedagogica(
    estado_practica: EstadoPracticaTutor,
    exploracion: Exploracion,
    evaluacion: EvaluacionTutor,
    policy: Dict[str, Any],
    adaptador: Optional[AdaptadorGemini],
) -> tuple[str, str]:
    """Elige y valida la siguiente acción pedagógica tras evaluar-respuesta."""
    limites = policy.get("limits") or {}
    max_turnos = int(limites.get("max_turnos", 5))
    max_intentos_act = int(limites.get("max_intentos_por_actividad", 3))
    max_pistas_act = int(limites.get("max_pistas_por_actividad", 2))
    max_pistas_tot = int(limites.get("max_pistas_totales", 4))
    max_refuerzos = int(limites.get("max_refuerzos", 2))

    permitidas = set(
        (policy.get("allowed_pedagogical_actions_by_state") or {}).get("EVALUADA") or []
    )
    puede_pista = (
        "OFRECER_PISTA" in permitidas
        and len(estado_practica.pistas_actividad_actual) < max_pistas_act
        and estado_practica.pistas_totales < max_pistas_tot
        and "dar-pista" in set(policy.get("enabled_skills") or [])
    )
    puede_refuerzo = (
        "PREPARAR_REFUERZO" in permitidas
        and estado_practica.refuerzos_realizados < max_refuerzos
        and estado_practica.turnos_consumidos < max_turnos
        and "preparar-actividad" in set(policy.get("enabled_skills") or [])
    )
    quedan_turnos = estado_practica.turnos_consumidos < max_turnos
    quedan_intentos_act = estado_practica.intentos_actividad_actual < max_intentos_act

    accion_propuesta: Optional[str] = None
    mensaje_transicion = ""

    # Consultar a Gemini para la decisión pedagógica cuando el adaptador está configurado
    if adaptador is not None and adaptador.esta_configurado:
        instrucciones = (
            "You are the HomeLens English tutor orchestrator ('orquestar-practica') choosing the next pedagogical action "
            "after 'evaluar-respuesta'. Choose one of: 'AVANZAR', 'PERMITIR_OTRO_INTENTO', 'OFRECER_PISTA', "
            "'PREPARAR_REFUERZO', or 'CERRAR', and provide a short transition message in Spanish ('mensaje_transicion')."
        )
        prompt_usr = (
            f"Evaluation: valoracion={evaluacion.valoracion}, dificultad={evaluacion.dificultad_detectada}, "
            f"objeto_confundido_id={evaluacion.objeto_confundido_id}\n"
            f"Turnos consumidos: {estado_practica.turnos_consumidos}/{max_turnos}\n"
            f"Intentos en actividad actual: {estado_practica.intentos_actividad_actual}/{max_intentos_act}\n"
            f"puede_pista={puede_pista}, puede_refuerzo={puede_refuerzo}\n"
            f"Total objects in photo: {len(exploracion.objetos)}, practiced: {len(estado_practica.objetos_practicados_ids)}"
        )
        res_dec = adaptador.generar_respuesta_estructurada(
            instrucciones=instrucciones,
            prompt_usuario=prompt_usr,
            esquema_respuesta=EsquemaDecisionOrquestadorIA,
            tipo_operacion="tutor_orquestar_decision_gemini",
        )
        if res_dec.ok and res_dec.valor is not None:
            dec_ia: EsquemaDecisionOrquestadorIA = res_dec.valor
            accion_propuesta = dec_ia.accion_siguiente
            mensaje_transicion = (dec_ia.mensaje_transicion or "").strip()

    # Validar que la acción propuesta por Gemini respete policy.json y el estado real; si no, aplicar regla determinista
    if evaluacion.valoracion == "CORRECTA":
        pendientes = [
            o for o in exploracion.objetos
            if str(o.objeto_id) not in set(estado_practica.objetos_practicados_ids)
        ]
        if accion_propuesta not in ("AVANZAR", "CERRAR"):
            accion_propuesta = "AVANZAR" if (quedan_turnos and pendientes) else "CERRAR"
        if accion_propuesta == "AVANZAR" and (not quedan_turnos or not pendientes):
            accion_propuesta = "CERRAR"
        if not mensaje_transicion:
            mensaje_transicion = (
                "¡Excelente! Puedes avanzar al siguiente objeto de tu fotografía."
                if accion_propuesta == "AVANZAR"
                else "¡Felicitaciones! Completaste la práctica guiada sobre tu fotografía."
            )
        return accion_propuesta, mensaje_transicion

    # Caso PARCIAL o INCORRECTA
    if not quedan_turnos:
        return "CERRAR", "Alcanzaste el límite de turnos de la práctica. ¡Buen esfuerzo!"

    if accion_propuesta == "PREPARAR_REFUERZO" and not puede_refuerzo:
        accion_propuesta = None
    if accion_propuesta == "OFRECER_PISTA" and not puede_pista:
        accion_propuesta = None
    if accion_propuesta == "PERMITIR_OTRO_INTENTO" and not quedan_intentos_act:
        accion_propuesta = None
    if accion_propuesta not in permitidas:
        accion_propuesta = None

    if accion_propuesta is None:
        if evaluacion.objeto_confundido_id and puede_refuerzo:
            accion_propuesta = "PREPARAR_REFUERZO"
        elif puede_pista and quedan_intentos_act:
            accion_propuesta = "OFRECER_PISTA"
        elif quedan_intentos_act:
            accion_propuesta = "PERMITIR_OTRO_INTENTO"
        elif puede_refuerzo:
            accion_propuesta = "PREPARAR_REFUERZO"
        else:
            accion_propuesta = "CERRAR"

    if not mensaje_transicion:
        mensajes_def = {
            "PREPARAR_REFUERZO": "El tutor preparó una consigna de refuerzo para ayudarte a distinguir los objetos de tu foto.",
            "OFRECER_PISTA": "El tutor te ofrece una pista para que vuelvas a intentarlo.",
            "PERMITIR_OTRO_INTENTO": "Puedes intentar nuevamente con otra respuesta.",
            "CERRAR": "Finalizó la ronda de intentos de esta práctica.",
        }
        mensaje_transicion = mensajes_def.get(accion_propuesta, "")

    return accion_propuesta, mensaje_transicion


def ejecutar_orquestar_practica(
    evento: Literal[
        "INICIAR_PRACTICA",
        "PEDIR_PISTA",
        "ENVIAR_RESPUESTA",
        "AVANZAR_ACTIVIDAD",
        "CERRAR_PRACTICA",
    ],
    estado_practica: EstadoPracticaTutor,
    exploracion: Exploracion,
    respuesta_alumno: Optional[str] = None,
    evento_id: Optional[str] = None,
    adaptador: Optional[AdaptadorGemini] = None,
    policy_override: Optional[Dict[str, Any]] = None,
) -> Resultado[EstadoPracticaTutor]:
    """Punto de entrada del Agente Tutor: valida política, coordina las 3 skills y actualiza sesión."""
    # 0. Guardia de idempotencia ante redibujados de Streamlit
    if evento_id and estado_practica.ultimo_evento_id_procesado == evento_id:
        return Resultado.exito(estado_practica)

    policy = policy_override or cargar_politica_tutor()
    habilitadas = set(policy.get("enabled_skills") or [])
    if "orquestar-practica" not in habilitadas:
        estado_practica.registrar_traza(
            evento_usuario=evento,
            skill_ejecutada="orquestar-practica",
            decision_politica="BLOQUEADA",
            accion_pedagogica="NINGUNA",
            resumen_observable="Política bloqueó orquestar-practica por no estar habilitada.",
        )
        return Resultado.fallo(
            codigo=CODIGO_ACCESO_DENEGADO,
            mensaje_usuario="La skill 'orquestar-practica' no está habilitada en policy.json.",
            reintentable=False,
        )

    if exploracion is None or not exploracion.objetos:
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario="La exploración activa no contiene objetos para practicar con el tutor.",
            reintentable=False,
        )

    # 1. Validar que el evento esté permitido en el estado actual según policy.json
    eventos_permitidos = set(
        (policy.get("allowed_events_by_state") or {}).get(estado_practica.estado) or []
    )
    if evento not in eventos_permitidos:
        resumen_bloq = (
            f"Usuario solicitó {evento} en estado {estado_practica.estado} → "
            f"orquestar-practica bloqueó la acción por policy.json"
        )
        estado_practica.error_actual = (
            f"La acción '{evento}' no está permitida cuando la práctica está en estado '{estado_practica.estado}'."
        )
        estado_practica.registrar_traza(
            evento_usuario=evento,
            skill_ejecutada="orquestar-practica",
            decision_politica="BLOQUEADA",
            accion_pedagogica="BLOQUEO_ESTADO",
            resumen_observable=resumen_bloq,
        )
        return Resultado.fallo(
            codigo=CODIGO_ACCESO_DENEGADO,
            mensaje_usuario=estado_practica.error_actual,
            reintentable=False,
        )

    limites = policy.get("limits") or {}
    max_turnos = int(limites.get("max_turnos", 5))
    max_intentos_act = int(limites.get("max_intentos_por_actividad", 3))
    max_pistas_act = int(limites.get("max_pistas_por_actividad", 2))
    max_pistas_tot = int(limites.get("max_pistas_totales", 4))

    # =================================================================
    # CASO A: CERRAR_PRACTICA (Salir del tutor y volver a la foto)
    # =================================================================
    if evento == "CERRAR_PRACTICA":
        estado_practica.estado = "FINALIZADA"
        estado_practica.error_actual = None
        estado_practica.mensaje_cierre = "Práctica con el tutor finalizada. Puedes seguir explorando tu fotografía."
        if evento_id:
            estado_practica.ultimo_evento_id_procesado = evento_id
        estado_practica.registrar_traza(
            evento_usuario="CERRAR_PRACTICA",
            skill_ejecutada="orquestar-practica",
            decision_politica="AUTORIZADA",
            accion_pedagogica="CERRAR",
            resumen_observable="Usuario cerró la práctica → orquestar-practica autorizó cierre → retorno a la misma foto",
        )
        return Resultado.exito(estado_practica)

    # =================================================================
    # CASO B: INICIAR_PRACTICA o AVANZAR_ACTIVIDAD -> preparar-actividad
    # =================================================================
    if evento in ("INICIAR_PRACTICA", "AVANZAR_ACTIVIDAD"):
        if evento == "INICIAR_PRACTICA" and estado_practica.estado == "FINALIZADA":
            estado_practica.turnos_consumidos = 0
            estado_practica.pistas_totales = 0
            estado_practica.refuerzos_realizados = 0
            estado_practica.objetos_practicados_ids = []
            estado_practica.historial_respuestas = []
            estado_practica.mensaje_cierre = None

        if estado_practica.turnos_consumidos >= max_turnos:
            estado_practica.error_actual = f"Se alcanzó el límite máximo de {max_turnos} turnos de la política."
            estado_practica.registrar_traza(
                evento_usuario=evento,
                skill_ejecutada="orquestar-practica",
                decision_politica="BLOQUEADA",
                accion_pedagogica="LIMITE_TURNOS",
                resumen_observable=f"Solicitud {evento} → bloqueada por límite de turnos ({max_turnos})",
            )
            return Resultado.fallo(
                codigo=CODIGO_LIMITE_ALCANZADO,
                mensaje_usuario=estado_practica.error_actual,
                reintentable=False,
            )

        mod_prep = cargar_ejecutor_skill("preparar-actividad", policy=policy)
        res_act = mod_prep.ejecutar_preparar_actividad(
            objetos_foto=exploracion.objetos,
            objetos_ya_practicados_ids=estado_practica.objetos_practicados_ids,
            modo_refuerzo=False,
            adaptador=adaptador,
            policy=policy,
        )
        if not res_act.ok or res_act.valor is None:
            estado_practica.error_actual = (
                res_act.error.mensaje_usuario if res_act.error else "No se pudo preparar la actividad."
            )
            decision = "BLOQUEADA" if (res_act.error and res_act.error.codigo == CODIGO_ACCESO_DENEGADO) else "AUTORIZADA"
            estado_practica.registrar_traza(
                evento_usuario=evento,
                skill_ejecutada="preparar-actividad",
                decision_politica=decision,
                accion_pedagogica="ERROR_PREPARACION",
                resumen_observable=f"{evento} → preparar-actividad falló o fue bloqueada: {estado_practica.error_actual}",
            )
            return Resultado.fallo(error=res_act.error)

        # Validar en el orquestador que todos los IDs pertenezcan a la foto activa
        actividad = res_act.valor
        val_ids = validar_ids_pertenecen_a_foto(
            list(actividad.objeto_ids) + [actividad.objeto_objetivo_id],
            exploracion.objetos,
        )
        if not val_ids.ok:
            estado_practica.error_actual = val_ids.error.mensaje_usuario if val_ids.error else "ID ajeno a la foto."
            estado_practica.registrar_traza(
                evento_usuario=evento,
                skill_ejecutada="preparar-actividad",
                decision_politica="BLOQUEADA",
                accion_pedagogica="BLOQUEO_ID_AJENO",
                resumen_observable=f"{evento} → orquestar-practica bloqueó ID ajeno a la foto activa",
            )
            return Resultado.fallo(error=val_ids.error)

        estado_practica.actividad_actual = actividad
        estado_practica.estado = "ESPERANDO_RESPUESTA"
        estado_practica.intentos_actividad_actual = 0
        estado_practica.pistas_actividad_actual = []
        estado_practica.ultima_evaluacion = None
        estado_practica.ultima_accion_pedagogica = "PREPARAR_ACTIVIDAD"
        estado_practica.mensaje_transicion = None
        estado_practica.objeto_resaltado_id = actividad.objeto_objetivo_id
        estado_practica.error_actual = None
        if evento_id:
            estado_practica.ultimo_evento_id_procesado = evento_id

        estado_practica.registrar_traza(
            evento_usuario=evento,
            skill_ejecutada="preparar-actividad",
            decision_politica="AUTORIZADA",
            accion_pedagogica="PREPARAR_ACTIVIDAD",
            resumen_observable=(
                f"Alumno solicitó {evento} → orquestar-practica autorizó preparar-actividad → "
                f"consigna preparada con {len(actividad.objeto_ids)} objeto(s) de la foto"
            ),
        )
        return Resultado.exito(estado_practica)

    # Verificar que exista actividad vigente para PEDIR_PISTA o ENVIAR_RESPUESTA
    actividad_vigente = estado_practica.actividad_actual
    if actividad_vigente is None:
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario="No hay una actividad activa en la práctica.",
            reintentable=False,
        )
    obj_objetivo = _obtener_objeto_por_id(exploracion, actividad_vigente.objeto_objetivo_id)
    if obj_objetivo is None:
        return Resultado.fallo(
            codigo=CODIGO_ACCESO_DENEGADO,
            mensaje_usuario="El objeto de la actividad no pertenece a la fotografía activa.",
            reintentable=False,
        )

    # =================================================================
    # CASO C: PEDIR_PISTA (Recorrido directo -> dar-pista)
    # =================================================================
    if evento == "PEDIR_PISTA":
        if (
            len(estado_practica.pistas_actividad_actual) >= max_pistas_act
            or estado_practica.pistas_totales >= max_pistas_tot
        ):
            estado_practica.error_actual = (
                f"Alcanzaste el límite de pistas permitido por la política "
                f"({max_pistas_act} por actividad, {max_pistas_tot} en total)."
            )
            estado_practica.registrar_traza(
                evento_usuario="PEDIR_PISTA",
                skill_ejecutada="orquestar-practica",
                decision_politica="BLOQUEADA",
                accion_pedagogica="LIMITE_PISTAS",
                resumen_observable=(
                    f"Alumno pidió pista → orquestar-practica bloqueó dar-pista por límite de policy.json "
                    f"({len(estado_practica.pistas_actividad_actual)}/{max_pistas_act})"
                ),
            )
            return Resultado.fallo(
                codigo=CODIGO_LIMITE_ALCANZADO,
                mensaje_usuario=estado_practica.error_actual,
                reintentable=False,
            )

        mod_pista = cargar_ejecutor_skill("dar-pista", policy=policy)
        ult_resp = (
            estado_practica.historial_respuestas[-1].get("respuesta")
            if estado_practica.historial_respuestas and estado_practica.intentos_actividad_actual > 0
            else None
        )
        ult_dif = (
            estado_practica.ultima_evaluacion.dificultad_detectada
            if estado_practica.ultima_evaluacion is not None
            else None
        )

        res_pista = mod_pista.ejecutar_dar_pista(
            consigna=actividad_vigente.consigna,
            objeto_objetivo=obj_objetivo,
            pistas_anteriores=[p.texto_pista for p in estado_practica.pistas_actividad_actual],
            respuesta_previa=ult_resp,
            dificultad_detectada=ult_dif,
            objetos_foto=exploracion.objetos,
            origen="SOLICITUD_ALUMNO",
            adaptador=adaptador,
        )
        if not res_pista.ok or res_pista.valor is None:
            estado_practica.error_actual = (
                res_pista.error.mensaje_usuario if res_pista.error else "No se pudo generar la pista."
            )
            return Resultado.fallo(error=res_pista.error)

        pista = res_pista.valor
        if pista.objeto_resaltado_id:
            val_res = validar_ids_pertenecen_a_foto([pista.objeto_resaltado_id], exploracion.objetos)
            if not val_res.ok:
                estado_practica.error_actual = val_res.error.mensaje_usuario if val_res.error else "ID inválido."
                estado_practica.registrar_traza(
                    evento_usuario="PEDIR_PISTA",
                    skill_ejecutada="dar-pista",
                    decision_politica="BLOQUEADA",
                    accion_pedagogica="BLOQUEO_ID_AJENO",
                    resumen_observable="Alumno pidió pista → orquestar-practica bloqueó objeto_resaltado_id ajeno a la foto",
                )
                return Resultado.fallo(error=val_res.error)
            estado_practica.objeto_resaltado_id = pista.objeto_resaltado_id

        estado_practica.pistas_actividad_actual.append(pista)
        estado_practica.pistas_totales += 1
        estado_practica.error_actual = None
        if evento_id:
            estado_practica.ultimo_evento_id_procesado = evento_id

        momento = (
            "antes de responder"
            if estado_practica.turnos_consumidos == 0
            else f"con {estado_practica.turnos_consumidos} respuesta(s) previa(s)"
        )
        conteo_txt = (
            "cero respuestas enviadas"
            if estado_practica.turnos_consumidos == 0
            else f"{estado_practica.turnos_consumidos} respuesta(s) enviadas"
        )
        estado_practica.registrar_traza(
            evento_usuario="PEDIR_PISTA",
            skill_ejecutada="dar-pista",
            decision_politica="AUTORIZADA",
            accion_pedagogica="OFRECER_PISTA",
            resumen_observable=(
                f"Alumno pidió ayuda {momento} → orquestar-practica autorizó dar-pista → "
                f"pista presentada → {conteo_txt}"
            ),
        )
        return Resultado.exito(estado_practica)

    # =================================================================
    # CASO D: ENVIAR_RESPUESTA (Directo -> evaluar-respuesta + decisión pedagógica)
    # =================================================================
    if estado_practica.turnos_consumidos >= max_turnos:
        estado_practica.error_actual = f"Alcanzaste el máximo de {max_turnos} turnos permitidos por la política."
        estado_practica.registrar_traza(
            evento_usuario="ENVIAR_RESPUESTA",
            skill_ejecutada="orquestar-practica",
            decision_politica="BLOQUEADA",
            accion_pedagogica="LIMITE_TURNOS",
            resumen_observable=f"Alumno envió respuesta → bloqueada por límite de turnos ({max_turnos})",
        )
        return Resultado.fallo(
            codigo=CODIGO_LIMITE_ALCANZADO,
            mensaje_usuario=estado_practica.error_actual,
            reintentable=False,
        )

    if estado_practica.intentos_actividad_actual >= max_intentos_act:
        estado_practica.error_actual = (
            f"Alcanzaste el máximo de {max_intentos_act} intentos para esta actividad."
        )
        estado_practica.registrar_traza(
            evento_usuario="ENVIAR_RESPUESTA",
            skill_ejecutada="orquestar-practica",
            decision_politica="BLOQUEADA",
            accion_pedagogica="LIMITE_INTENTOS_ACTIVIDAD",
            resumen_observable=f"Alumno envió respuesta → bloqueada por límite de intentos ({max_intentos_act})",
        )
        return Resultado.fallo(
            codigo=CODIGO_LIMITE_ALCANZADO,
            mensaje_usuario=estado_practica.error_actual,
            reintentable=False,
        )

    objetos_act = [
        o for o in exploracion.objetos if str(o.objeto_id) in set(actividad_vigente.objeto_ids)
    ] or [obj_objetivo]

    mod_eval = cargar_ejecutor_skill("evaluar-respuesta", policy=policy)
    res_eval = mod_eval.ejecutar_evaluar_respuesta(
        consigna=actividad_vigente.consigna,
        objetos_actividad=objetos_act,
        objeto_objetivo=obj_objetivo,
        criterio_correccion=actividad_vigente.criterio_correccion,
        respuesta_alumno=respuesta_alumno or "",
        respuestas_aceptadas=actividad_vigente.respuestas_aceptadas,
        todos_objetos_foto=exploracion.objetos,
        adaptador=adaptador,
        policy=policy,
    )
    if not res_eval.ok or res_eval.valor is None:
        estado_practica.error_actual = (
            res_eval.error.mensaje_usuario if res_eval.error else "No se pudo evaluar la respuesta."
        )
        return Resultado.fallo(error=res_eval.error)

    evaluacion = res_eval.valor
    if evaluacion.objeto_confundido_id:
        val_conf = validar_ids_pertenecen_a_foto([evaluacion.objeto_confundido_id], exploracion.objetos)
        if not val_conf.ok:
            estado_practica.error_actual = val_conf.error.mensaje_usuario if val_conf.error else "ID inválido."
            return Resultado.fallo(error=val_conf.error)

    # Consumir turno recién cuando la evaluación se completó sin fallo técnico
    estado_practica.turnos_consumidos += 1
    estado_practica.intentos_actividad_actual += 1
    estado_practica.ultima_evaluacion = evaluacion
    estado_practica.estado = "EVALUADA"
    estado_practica.error_actual = None

    if evaluacion.valoracion == "CORRECTA":
        if str(obj_objetivo.objeto_id) not in estado_practica.objetos_practicados_ids:
            estado_practica.objetos_practicados_ids.append(str(obj_objetivo.objeto_id))

    estado_practica.historial_respuestas.append(
        {
            "actividad_tutor_id": actividad_vigente.actividad_tutor_id,
            "objeto_objetivo_id": str(obj_objetivo.objeto_id),
            "respuesta": (respuesta_alumno or "").strip(),
            "valoracion": evaluacion.valoracion,
            "dificultad_detectada": evaluacion.dificultad_detectada,
            "objeto_confundido_id": evaluacion.objeto_confundido_id,
        }
    )

    # Decisión pedagógica posterior a evaluar-respuesta
    accion_ped, msg_trans = _decidir_accion_pedagogica(
        estado_practica=estado_practica,
        exploracion=exploracion,
        evaluacion=evaluacion,
        policy=policy,
        adaptador=adaptador,
    )
    estado_practica.ultima_accion_pedagogica = accion_ped
    estado_practica.mensaje_transicion = msg_trans

    estado_practica.registrar_traza(
        evento_usuario="ENVIAR_RESPUESTA",
        skill_ejecutada="evaluar-respuesta",
        decision_politica="AUTORIZADA",
        accion_pedagogica=accion_ped,
        resumen_observable=(
            f"Alumno envió respuesta → orquestar-practica autorizó evaluar-respuesta ({evaluacion.valoracion}) "
            f"→ tutor decidió acción pedagógica {accion_ped}"
        ),
    )

    # Ejecutar automáticamente la skill secundaria si la acción pedagógica fue OFRECER_PISTA o PREPARAR_REFUERZO
    if accion_ped == "OFRECER_PISTA":
        mod_pista = cargar_ejecutor_skill("dar-pista", policy=policy)
        res_p = mod_pista.ejecutar_dar_pista(
            consigna=actividad_vigente.consigna,
            objeto_objetivo=obj_objetivo,
            pistas_anteriores=[p.texto_pista for p in estado_practica.pistas_actividad_actual],
            respuesta_previa=(respuesta_alumno or "").strip(),
            dificultad_detectada=evaluacion.dificultad_detectada,
            objetos_foto=exploracion.objetos,
            origen="DECISION_TUTOR",
            adaptador=adaptador,
        )
        if res_p.ok and res_p.valor is not None:
            pista_auto = res_p.valor
            if pista_auto.objeto_resaltado_id:
                val_p = validar_ids_pertenecen_a_foto([pista_auto.objeto_resaltado_id], exploracion.objetos)
                if val_p.ok:
                    estado_practica.objeto_resaltado_id = pista_auto.objeto_resaltado_id
            estado_practica.pistas_actividad_actual.append(pista_auto)
            estado_practica.pistas_totales += 1
            estado_practica.estado = "ESPERANDO_RESPUESTA"
            estado_practica.registrar_traza(
                evento_usuario="DECISION_TUTOR",
                skill_ejecutada="dar-pista",
                decision_politica="AUTORIZADA",
                accion_pedagogica="OFRECER_PISTA",
                resumen_observable="Tutor ofreció pista tras evaluación → dar-pista ejecutada → alumno puede reintentar",
            )

    elif accion_ped == "PREPARAR_REFUERZO":
        mod_prep = cargar_ejecutor_skill("preparar-actividad", policy=policy)
        res_ref = mod_prep.ejecutar_preparar_actividad(
            objetos_foto=exploracion.objetos,
            objetos_ya_practicados_ids=estado_practica.objetos_practicados_ids,
            modo_refuerzo=True,
            dificultad_previa=evaluacion.dificultad_detectada,
            objeto_objetivo_forzado_id=str(obj_objetivo.objeto_id),
            objeto_confundido_id=evaluacion.objeto_confundido_id,
            adaptador=adaptador,
            policy=policy,
        )
        if res_ref.ok and res_ref.valor is not None:
            act_ref = res_ref.valor
            val_ref = validar_ids_pertenecen_a_foto(
                list(act_ref.objeto_ids) + [act_ref.objeto_objetivo_id],
                exploracion.objetos,
            )
            if val_ref.ok:
                estado_practica.actividad_actual = act_ref
                estado_practica.refuerzos_realizados += 1
                estado_practica.intentos_actividad_actual = 0
                estado_practica.pistas_actividad_actual = []
                estado_practica.estado = "ESPERANDO_RESPUESTA"
                estado_practica.objeto_resaltado_id = act_ref.objeto_objetivo_id
                estado_practica.registrar_traza(
                    evento_usuario="DECISION_TUTOR",
                    skill_ejecutada="preparar-actividad",
                    decision_politica="AUTORIZADA",
                    accion_pedagogica="PREPARAR_REFUERZO",
                    resumen_observable=(
                        "Tutor detectó confusión/dificultad → preparar-actividad generó consigna de refuerzo "
                        f"con {len(act_ref.objeto_ids)} objeto(s) de la foto"
                    ),
                )

    elif accion_ped == "PERMITIR_OTRO_INTENTO":
        estado_practica.estado = "ESPERANDO_RESPUESTA"

    elif accion_ped == "CERRAR":
        estado_practica.estado = "FINALIZADA"
        estado_practica.mensaje_cierre = msg_trans or "Práctica con el tutor completada."

    if evento_id:
        estado_practica.ultimo_evento_id_procesado = evento_id

    return Resultado.exito(estado_practica)
