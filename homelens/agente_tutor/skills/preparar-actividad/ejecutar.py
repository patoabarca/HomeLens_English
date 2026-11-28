"""Ejecutor real de la skill preparar-actividad del Agente Tutor."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from homelens.agente_tutor.cargador import (
    cargar_politica_tutor,
    validar_ids_pertenecen_a_foto,
)
from homelens.agente_tutor.contratos import (
    ActividadTutor,
    EsquemaActividadTutorIA,
)
from homelens.errores import (
    CODIGO_IMAGEN_INVALIDA,
    CODIGO_RESPUESTA_INVALIDA,
    Resultado,
)
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import ObjetoEducativo


def _seleccionar_objetos_candidatos(
    objetos_foto: Sequence[ObjetoEducativo],
    objetos_ya_practicados_ids: Optional[Sequence[str]],
    objeto_objetivo_forzado_id: Optional[str],
    objeto_confundido_id: Optional[str],
    max_objetos: int,
) -> tuple[ObjetoEducativo, List[ObjetoEducativo]]:
    """Selecciona el objeto objetivo y hasta max_objetos (1..3) de la foto activa."""
    mapa = {str(o.objeto_id): o for o in objetos_foto}
    practicados = set(str(x) for x in (objetos_ya_practicados_ids or []))

    objetivo: Optional[ObjetoEducativo] = None
    if objeto_objetivo_forzado_id and str(objeto_objetivo_forzado_id) in mapa:
        objetivo = mapa[str(objeto_objetivo_forzado_id)]
    else:
        for obj in objetos_foto:
            if str(obj.objeto_id) not in practicados:
                objetivo = obj
                break
        if objetivo is None:
            objetivo = objetos_foto[0]

    seleccionados: List[ObjetoEducativo] = [objetivo]
    if objeto_confundido_id and str(objeto_confundido_id) in mapa:
        conf = mapa[str(objeto_confundido_id)]
        if str(conf.objeto_id) != str(objetivo.objeto_id):
            seleccionados.append(conf)

    for obj in objetos_foto:
        if len(seleccionados) >= max_objetos:
            break
        if all(str(obj.objeto_id) != str(s.objeto_id) for s in seleccionados):
            seleccionados.append(obj)

    return objetivo, seleccionados[:max_objetos]


def _construir_variantes_aceptadas(obj: ObjetoEducativo) -> List[str]:
    base = obj.nombre_en.strip().lower()
    variantes = [base, f"a {base}", f"an {base}", f"the {base}"]
    partes = base.split()
    if len(partes) > 1:
        nucleo = partes[-1]
        variantes.extend([nucleo, f"a {nucleo}", f"the {nucleo}"])
    return list(dict.fromkeys(v for v in variantes if v))


def ejecutar_preparar_actividad(
    objetos_foto: Sequence[ObjetoEducativo],
    objetos_ya_practicados_ids: Optional[Sequence[str]] = None,
    modo_refuerzo: bool = False,
    dificultad_previa: Optional[str] = None,
    objeto_objetivo_forzado_id: Optional[str] = None,
    objeto_confundido_id: Optional[str] = None,
    adaptador: Optional[AdaptadorGemini] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Resultado[ActividadTutor]:
    """Prepara una actividad breve o de refuerzo con entre 1 y 3 objetos de la foto activa."""
    if not objetos_foto:
        return Resultado.fallo(
            codigo=CODIGO_IMAGEN_INVALIDA,
            mensaje_usuario="No hay objetos detectados en la fotografía activa para preparar una actividad.",
            reintentable=False,
        )

    pol = policy or cargar_politica_tutor()
    limites = pol.get("limits") or {}
    min_obj = int(limites.get("min_objetos_actividad", 1))
    max_obj = int(limites.get("max_objetos_actividad", 3))

    # Validar de antemano si se pasaron IDs forzados que no pertenecen a la foto activa
    ids_forzados = [x for x in (objeto_objetivo_forzado_id, objeto_confundido_id) if x]
    if ids_forzados:
        val_forzados = validar_ids_pertenecen_a_foto(ids_forzados, objetos_foto)
        if not val_forzados.ok:
            return Resultado.fallo(error=val_forzados.error)

    objetivo_def, seleccionados_def = _seleccionar_objetos_candidatos(
        objetos_foto=objetos_foto,
        objetos_ya_practicados_ids=objetos_ya_practicados_ids,
        objeto_objetivo_forzado_id=objeto_objetivo_forzado_id,
        objeto_confundido_id=objeto_confundido_id,
        max_objetos=max_obj,
    )

    # Si hay adaptador de Gemini configurado, solicitar formulación estructurada con Pydantic
    if adaptador is not None and adaptador.esta_configurado:
        catalogo_prompt = [
            {
                "objeto_id": str(o.objeto_id),
                "nombre_en": o.nombre_en,
                "nombre_es": o.nombre_es,
                "frase_en": o.frase_en,
                "frase_es": o.frase_es,
            }
            for o in seleccionados_def
        ]
        instrucciones = (
            "You are the HomeLens English vocabulary tutor agent executing the skill 'preparar-actividad'. "
            f"Choose between {min_obj} and {min(max_obj, len(seleccionados_def))} objects ONLY from the provided list "
            "(using their exact 'objeto_id'). Formulate a short, clear question in Spanish ('consigna') asking the student "
            "to write in English the name of the target object ('objeto_objetivo_id') without revealing its English word in 'consigna'. "
            "If 'modo_refuerzo' is True, craft a contrastive prompt helping the learner distinguish the confused objects."
        )
        prompt_usr = (
            f"Available objects from active photo: {catalogo_prompt}\n"
            f"Preferred target object_id: {objetivo_def.objeto_id}\n"
            f"Confused object_id: {objeto_confundido_id}\n"
            f"modo_refuerzo: {modo_refuerzo}\n"
            f"dificultad_previa: {dificultad_previa or 'ninguna'}"
        )
        res_ia = adaptador.generar_respuesta_estructurada(
            instrucciones=instrucciones,
            prompt_usuario=prompt_usr,
            esquema_respuesta=EsquemaActividadTutorIA,
            tipo_operacion="tutor_preparar_actividad_gemini",
        )
        if not res_ia.ok or res_ia.valor is None:
            return Resultado.fallo(error=res_ia.error)

        datos_ia: EsquemaActividadTutorIA = res_ia.valor

        # Validar política: todos los IDs devueltos por Gemini deben pertenecer a la foto activa
        todos_ids_ia = list(datos_ia.objeto_ids_elegidos or []) + [datos_ia.objeto_objetivo_id]
        val_ids = validar_ids_pertenecen_a_foto(todos_ids_ia, objetos_foto)
        if not val_ids.ok:
            return Resultado.fallo(error=val_ids.error)

        ids_elegidos = list(dict.fromkeys(str(x).strip() for x in datos_ia.objeto_ids_elegidos if str(x).strip()))
        obj_id_str = str(datos_ia.objeto_objetivo_id).strip()
        if obj_id_str not in ids_elegidos:
            ids_elegidos.insert(0, obj_id_str)

        if not (min_obj <= len(ids_elegidos) <= max_obj):
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"La actividad preparada tiene {len(ids_elegidos)} objetos (permitido: {min_obj} a {max_obj}).",
                reintentable=False,
            )

        mapa_foto = {str(o.objeto_id): o for o in objetos_foto}
        obj_meta = mapa_foto[obj_id_str]
        aceptadas = list(
            dict.fromkeys(
                [r.strip().lower() for r in (datos_ia.respuestas_aceptadas or []) if r and r.strip()]
                + _construir_variantes_aceptadas(obj_meta)
            )
        )
        consigna_limpia = (datos_ia.consigna or "").strip()
        if not consigna_limpia:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario="Gemini devolvió una consigna vacía al preparar la actividad.",
                reintentable=False,
            )

        return Resultado.exito(
            ActividadTutor(
                actividad_tutor_id=str(uuid4()),
                consigna=consigna_limpia,
                objeto_ids=ids_elegidos,
                objeto_objetivo_id=obj_id_str,
                criterio_correccion=(datos_ia.criterio_correccion or "").strip()
                or f"El alumno debe nombrar en inglés '{obj_meta.nombre_en}' ({obj_meta.nombre_es}).",
                respuestas_aceptadas=aceptadas,
                es_refuerzo=bool(modo_refuerzo or datos_ia.es_refuerzo),
                foco_dificultad=dificultad_previa,
            )
        )

    # Construcción determinista local (respaldo cuando se opera sin cliente Gemini)
    ids_seleccionados = [str(o.objeto_id) for o in seleccionados_def]
    val_local = validar_ids_pertenecen_a_foto(ids_seleccionados, objetos_foto)
    if not val_local.ok:
        return Resultado.fallo(error=val_local.error)

    if modo_refuerzo and len(seleccionados_def) >= 2:
        otro = seleccionados_def[1]
        consigna = (
            f"Refuerzo de vocabulario: en tu foto aparecen «{objetivo_def.nombre_es}» y «{otro.nombre_es}». "
            f"Para distinguirlos, ¿cómo se escribe en inglés únicamente «{objetivo_def.nombre_es}»?"
        )
    elif modo_refuerzo:
        consigna = (
            f"Refuerzo de vocabulario: volvamos a observar el objeto «{objetivo_def.nombre_es}» en tu foto. "
            f"¿Cómo se nombra este objeto en inglés?"
        )
    else:
        consigna = (
            f"Observa tu fotografía: ¿cómo se dice en inglés «{objetivo_def.nombre_es}»?"
        )

    criterio = (
        f"Aceptar '{objetivo_def.nombre_en}' (con o sin artículo 'a/an/the' y variantes equivalentes en contexto) "
        f"para el objeto '{objetivo_def.nombre_es}'."
    )

    return Resultado.exito(
        ActividadTutor(
            actividad_tutor_id=str(uuid4()),
            consigna=consigna,
            objeto_ids=ids_seleccionados,
            objeto_objetivo_id=str(objetivo_def.objeto_id),
            criterio_correccion=criterio,
            respuestas_aceptadas=_construir_variantes_aceptadas(objetivo_def),
            es_refuerzo=modo_refuerzo,
            foco_dificultad=dificultad_previa,
        )
    )
