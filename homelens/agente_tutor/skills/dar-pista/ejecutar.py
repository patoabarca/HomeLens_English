"""Ejecutor real de la skill dar-pista del Agente Tutor."""

from __future__ import annotations
from typing import Literal, Optional, Sequence

from homelens.agente_tutor.cargador import validar_ids_pertenecen_a_foto
from homelens.agente_tutor.contratos import EsquemaPistaTutorIA, PistaTutor
from homelens.errores import CODIGO_RESPUESTA_INVALIDA, Resultado
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import ObjetoEducativo


def _generar_pista_progresiva_local(
    objeto_objetivo: ObjetoEducativo,
    pistas_anteriores: Sequence[str],
    dificultad_detectada: Optional[str],
) -> str:
    """Construye una pista diferente según cuántas pistas ya se otorgaron."""
    palabra = objeto_objetivo.nombre_en.strip()
    inicial = palabra[0].upper() if palabra else ""
    largo = len(palabra)
    anteriores_norm = {p.strip().lower() for p in pistas_anteriores if p}

    candidatas = [
        (
            f"Pista 1: observa el objeto resaltado en la foto («{objeto_objetivo.nombre_es}»). "
            f"En inglés comienza con la letra «{inicial}» y tiene {largo} caracteres."
        ),
        (
            f"Pista 2: piensa en el ejemplo «{objeto_objetivo.frase_es}». "
            f"La palabra en inglés empieza con «{palabra[:2]}...»."
        ),
        (
            f"Pista adicional ({dificultad_detectada or 'vocabulario'}): "
            f"sus letras iniciales son «{palabra[:3]}...» para decir «{objeto_objetivo.nombre_es}»."
        ),
    ]
    for cand in candidatas:
        if cand.strip().lower() not in anteriores_norm:
            return cand
    return f"Pista #{len(pistas_anteriores) + 1}: comienza con «{inicial}» ({largo} caracteres)."


def ejecutar_dar_pista(
    consigna: str,
    objeto_objetivo: ObjetoEducativo,
    pistas_anteriores: Sequence[str],
    respuesta_previa: Optional[str] = None,
    dificultad_detectada: Optional[str] = None,
    objetos_foto: Optional[Sequence[ObjetoEducativo]] = None,
    origen: Literal["SOLICITUD_ALUMNO", "DECISION_TUTOR"] = "SOLICITUD_ALUMNO",
    adaptador: Optional[AdaptadorGemini] = None,
) -> Resultado[PistaTutor]:
    """Genera una pista breve y diferente de las anteriores, devolviendo el ID a resaltar."""
    if objeto_objetivo is None or not (objeto_objetivo.nombre_en or "").strip():
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario="No se indicó un objeto válido para generar la pista.",
            reintentable=False,
        )

    lista_foto = list(objetos_foto) if objetos_foto is not None else [objeto_objetivo]
    val_obj = validar_ids_pertenecen_a_foto([str(objeto_objetivo.objeto_id)], lista_foto)
    if not val_obj.ok:
        return Resultado.fallo(error=val_obj.error)

    numero_pista = len(pistas_anteriores) + 1

    if adaptador is not None and adaptador.esta_configurado:
        instrucciones = (
            "You are the HomeLens English vocabulary tutor executing the independent skill 'dar-pista'. "
            "Provide a short, encouraging hint in Spanish ('texto_pista') that helps the learner try again "
            "WITHOUT revealing the full English target word. "
            "If 'pistas_anteriores' is non-empty, your hint MUST be different and more specific than previous hints. "
            "Return 'objeto_resaltado_id' with the target object's ID so the UI can highlight its bounding box."
        )
        prompt_usr = (
            f"Consigna: {consigna}\n"
            f"Target object: id={objeto_objetivo.objeto_id}, en={objeto_objetivo.nombre_en}, "
            f"es={objeto_objetivo.nombre_es}, example_es={objeto_objetivo.frase_es}\n"
            f"Previous hints given: {list(pistas_anteriores)}\n"
            f"Student's previous answer (optional): {respuesta_previa}\n"
            f"Detected difficulty (optional): {dificultad_detectada}"
        )
        res_ia = adaptador.generar_respuesta_estructurada(
            instrucciones=instrucciones,
            prompt_usuario=prompt_usr,
            esquema_respuesta=EsquemaPistaTutorIA,
            tipo_operacion="tutor_dar_pista_gemini",
        )
        if not res_ia.ok or res_ia.valor is None:
            return Resultado.fallo(error=res_ia.error)

        datos_ia: EsquemaPistaTutorIA = res_ia.valor
        resaltado_id = (datos_ia.objeto_resaltado_id or str(objeto_objetivo.objeto_id)).strip()

        val_resaltado = validar_ids_pertenecen_a_foto([resaltado_id], lista_foto)
        if not val_resaltado.ok:
            return Resultado.fallo(error=val_resaltado.error)

        texto_ia = (datos_ia.texto_pista or "").strip()
        anteriores_norm = {p.strip().lower() for p in pistas_anteriores if p}
        if not texto_ia or texto_ia.lower() in anteriores_norm:
            texto_ia = _generar_pista_progresiva_local(
                objeto_objetivo=objeto_objetivo,
                pistas_anteriores=pistas_anteriores,
                dificultad_detectada=dificultad_detectada,
            )

        return Resultado.exito(
            PistaTutor(
                numero_pista=numero_pista,
                texto_pista=texto_ia,
                objeto_resaltado_id=resaltado_id,
                origen=origen,
            )
        )

    texto_local = _generar_pista_progresiva_local(
        objeto_objetivo=objeto_objetivo,
        pistas_anteriores=pistas_anteriores,
        dificultad_detectada=dificultad_detectada,
    )
    return Resultado.exito(
        PistaTutor(
            numero_pista=numero_pista,
            texto_pista=texto_local,
            objeto_resaltado_id=str(objeto_objetivo.objeto_id),
            origen=origen,
        )
    )
