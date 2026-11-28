"""Pruebas automatizadas del Agente Tutor y sus 4 skills ejecutables.

Todas las pruebas utilizan respuestas simuladas de Gemini (sin llamadas reales a la API)
para verificar:
1. Que el recorrido habitual (exploración, tarjetas y cuestionario) funcione sin activar
   al tutor ni generar llamadas adicionales a Gemini.
2. Que un alumno inicie la práctica y pida una pista antes de responder (`PEDIR_PISTA`),
   ejecutando `dar-pista` una sola vez, con `turnos_consumidos == 0`, resaltando el recuadro
   en la foto y dejando la traza observable para la defensa.
3. Que una respuesta correcta (`CORRECTA`) permita avanzar (`AVANZAR` -> `AVANZAR_ACTIVIDAD`).
4. Que una respuesta incorrecta (`INCORRECTA`) reciba una pista (`OFRECER_PISTA`) o active
   un ejercicio de refuerzo contrastivo (`PREPARAR_REFUERZO`) cuando confunde dos objetos.
5. Que la práctica funcione con un solo objeto en la foto, y que un ID ajeno a la foto
   o una acción fuera de los límites de `policy.json` quede bloqueada.
6. Que una recarga (rerun) de Streamlit con el mismo `evento_id` no duplique llamadas
   ni consuma turnos, que un fallo permita reintentar sin duplicar el intento, y que al
   salir del tutor el usuario vuelva a la misma exploración de la foto.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
from streamlit.testing.v1 import AppTest

from homelens.agente_tutor.cargador import (
    cargar_definicion_skill,
    cargar_ejecutor_skill,
    cargar_politica_tutor,
    validar_ids_pertenecen_a_foto,
)
from homelens.agente_tutor.contratos import (
    EsquemaActividadTutorIA,
    EsquemaDecisionOrquestadorIA,
    EsquemaEvaluacionTutorIA,
    EsquemaPistaTutorIA,
    EstadoPracticaTutor,
)
from homelens.errores import (
    CODIGO_ACCESO_DENEGADO,
    CODIGO_LIMITE_ALCANZADO,
    CODIGO_SERVICIO_NO_DISPONIBLE,
    Resultado,
)
from homelens.exploracion import construir_tarjetas
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import (
    Actividad,
    ContextoUsuario,
    EstadoAnalisis,
    Exploracion,
    ObjetoEducativo,
    Opcion,
    RecuadroNormalizado,
    ResultadoIntento,
)
from homelens.practicas import obtener_actividad_publica, validar_y_responder_actividad


# ==========================================
# Helpers y dobles de prueba (Gemini simulado)
# ==========================================

SKILLS_REQUERIDAS = [
    "orquestar-practica",
    "preparar-actividad",
    "evaluar-respuesta",
    "dar-pista",
]


def _crear_objeto(
    exploracion_id,
    nombre_en: str,
    nombre_es: str,
    frase_en: str = "This is an example sentence in English.",
    frase_es: str = "Esta es una oración de ejemplo en español.",
    ymin: int = 100,
    xmin: int = 100,
    ymax: int = 500,
    xmax: int = 500,
) -> ObjetoEducativo:
    return ObjetoEducativo(
        objeto_id=uuid4(),
        exploracion_id=exploracion_id,
        nombre_en=nombre_en,
        nombre_es=nombre_es,
        recuadro=RecuadroNormalizado(ymin=ymin, xmin=xmin, ymax=ymax, xmax=xmax),
        frase_en=frase_en,
        frase_es=frase_es,
    )


def _crear_exploracion_prueba(cantidad_objetos: int = 3) -> Exploracion:
    exp_id = uuid4()
    catalogo = [
        ("coffee mug", "taza de café", "The coffee mug is next to the laptop.", "La taza de café está junto a la laptop."),
        ("wooden chair", "silla de madera", "The wooden chair is near the desk.", "La silla de madera está cerca del escritorio."),
        ("desk lamp", "lámpara de escritorio", "The desk lamp lights the room.", "La lámpara de escritorio ilumina la habitación."),
    ]
    objetos = [
        _crear_objeto(
            exp_id,
            en,
            es,
            ej_en,
            ej_es,
            ymin=100 * (i + 1),
            xmin=100 * (i + 1),
            ymax=200 * (i + 2),
            xmax=200 * (i + 2),
        )
        for i, (en, es, ej_en, ej_es) in enumerate(catalogo[:cantidad_objetos])
    ]
    obj_principal = objetos[0]
    actividades = [
        Actividad(
            actividad_id=uuid4(),
            exploracion_id=exp_id,
            objeto_ids=[obj_principal.objeto_id],
            pregunta=f"¿Cómo se dice «{obj_principal.nombre_es}» en inglés?",
            opciones=[
                Opcion(opcion_id="A", texto=obj_principal.nombre_en),
                Opcion(opcion_id="B", texto="window"),
                Opcion(opcion_id="C", texto="carpet"),
            ],
            opcion_correcta_id="A",
            explicacion=f"«{obj_principal.nombre_en}» significa «{obj_principal.nombre_es}».",
        ),
    ]
    return Exploracion(
        exploracion_id=exp_id,
        user_id=uuid4(),
        creada_en=datetime.now(timezone.utc),
        estado=EstadoAnalisis.UTILIZABLE,
        objetos=objetos,
        actividades=actividades,
    )


class AdaptadorGeminiTutorSimulado(AdaptadorGemini):
    """Adaptador simulado que intercepta `generar_respuesta_estructurada` sin llamadas de red."""

    def __init__(
        self,
        resolvedor: Optional[Callable[[str, Any], Resultado[Any]]] = None,
    ) -> None:
        super().__init__(
            api_key="AIzaSyFakeKeyForTutorTests",
            modelo="gemini-2.5-flash",
            timeout_segundos=5,
            max_reintentos=0,
        )
        self.llamadas: List[Dict[str, Any]] = []
        self._resolvedor = resolvedor

    @property
    def esta_configurado(self) -> bool:
        return True

    def generar_respuesta_estructurada(
        self,
        instrucciones: str,
        prompt_usuario: str,
        esquema_respuesta: Any,
        tipo_operacion: str = "agente_tutor_gemini",
        operacion_id: Optional[Any] = None,
        usuario: Optional[ContextoUsuario] = None,
        repositorio: Optional[Any] = None,
    ) -> Resultado[Any]:
        self.llamadas.append(
            {
                "tipo_operacion": tipo_operacion,
                "esquema": getattr(esquema_respuesta, "__name__", str(esquema_respuesta)),
                "instrucciones": instrucciones,
                "prompt_usuario": prompt_usuario,
            }
        )
        if self._resolvedor is not None:
            return self._resolvedor(tipo_operacion, esquema_respuesta)
        raise AssertionError(f"Llamada no esperada a {tipo_operacion}")


# ==========================================
# 1. Recorrido habitual sin activar el tutor
# ==========================================


def test_recorrido_habitual_no_activa_tutor_ni_llama_gemini():
    """Quien prefiere el recorrido habitual explora tarjetas y completa el cuestionario sin activar al tutor."""
    exploracion = _crear_exploracion_prueba(3)
    adaptador_espia = AdaptadorGeminiTutorSimulado()

    # 1. Explorar objetos y tarjetas educativas habituales
    tarjetas = construir_tarjetas(exploracion)
    assert len(tarjetas) == 3
    assert tarjetas[0].nombre_en == "coffee mug"
    assert tarjetas[0].nombre_es == "taza de café"

    # 2. Completar el cuestionario habitual
    usuario = ContextoUsuario(user_id=exploracion.user_id, sesion_id="ses-habitual", email="alumno@test.com")
    actividad = exploracion.actividades[0]
    vista_pub = obtener_actividad_publica(actividad)
    assert vista_pub.actividad_id == actividad.actividad_id

    res_quiz = validar_y_responder_actividad(
        usuario=usuario,
        actividad=actividad,
        opcion_id="A",
    )
    assert res_quiz.ok and res_quiz.valor is not None
    assert res_quiz.valor.resultado == ResultadoIntento.CORRECTO

    # Cero llamadas al adaptador de Gemini del tutor
    assert len(adaptador_espia.llamadas) == 0


def test_estructura_skills_y_separacion_vista_alumno():
    """Verifica que las 4 skills tengan SKILL.md válido, ejecutar.py y que vista_alumno oculte respuestas."""
    policy = cargar_politica_tutor()
    assert set(policy["enabled_skills"]) == set(SKILLS_REQUERIDAS)

    for nombre_skill in SKILLS_REQUERIDAS:
        definicion = cargar_definicion_skill(nombre_skill)
        assert definicion.name == nombre_skill
        assert definicion.description
        modulo = cargar_ejecutor_skill(nombre_skill)
        assert modulo is not None

    exploracion = _crear_exploracion_prueba(2)
    mod_prep = cargar_ejecutor_skill("preparar-actividad")
    res_act = mod_prep.ejecutar_preparar_actividad(objetos_foto=exploracion.objetos)
    assert res_act.ok and res_act.valor is not None
    actividad = res_act.valor

    # Internamente tiene respuestas_aceptadas y criterio_correccion
    assert len(actividad.respuestas_aceptadas) >= 1
    assert actividad.criterio_correccion

    # La vista pública para el alumno NUNCA incluye respuestas_aceptadas ni criterio_correccion
    vista = actividad.vista_alumno()
    assert "consigna" in vista
    assert "objeto_ids" in vista
    assert "respuestas_aceptadas" not in vista
    assert "criterio_correccion" not in vista


# ==========================================
# 2. Caso «Dame una pista antes de responder»
# ==========================================


def test_pedir_pista_antes_de_responder_ejecuta_dar_pista_sin_consumir_turno():
    """El alumno inicia la práctica y pide una pista antes de responder:
    dar-pista se ejecuta una sola vez, turnos_consumidos queda en 0, se resalta el objeto
    y se registra la traza observable para la defensa.
    """
    exploracion = _crear_exploracion_prueba(3)
    obj_mug = exploracion.objetos[0]

    def resolvedor(tipo_operacion: str, esquema: Any) -> Resultado[Any]:
        if tipo_operacion == "tutor_preparar_actividad_gemini":
            return Resultado.exito(
                EsquemaActividadTutorIA(
                    consigna="¿Cómo se escribe en inglés el objeto «taza de café» (#1)?",
                    objeto_ids_elegidos=[str(obj_mug.objeto_id)],
                    objeto_objetivo_id=str(obj_mug.objeto_id),
                    criterio_correccion="Aceptar coffee mug o mug.",
                    respuestas_aceptadas=["coffee mug", "mug"],
                    es_refuerzo=False,
                )
            )
        if tipo_operacion == "tutor_dar_pista_gemini":
            return Resultado.exito(
                EsquemaPistaTutorIA(
                    texto_pista="Observa el objeto #1 («taza de café»): en inglés comienza con «C».",
                    objeto_resaltado_id=str(obj_mug.objeto_id),
                )
            )
        raise AssertionError(f"Operación inesperada: {tipo_operacion}")

    adaptador = AdaptadorGeminiTutorSimulado(resolvedor=resolvedor)
    estado = EstadoPracticaTutor(exploracion_id=str(exploracion.exploracion_id))
    mod_orq = cargar_ejecutor_skill("orquestar-practica")

    # Paso 1: Iniciar práctica
    res_inicio = mod_orq.ejecutar_orquestar_practica(
        evento="INICIAR_PRACTICA",
        estado_practica=estado,
        exploracion=exploracion,
        evento_id="ev-inicio-1",
        adaptador=adaptador,
    )
    assert res_inicio.ok
    assert estado.turnos_consumidos == 0
    assert estado.pistas_totales == 0

    # Paso 2: El alumno toca «Dame una pista» antes de enviar respuesta
    res_pista = mod_orq.ejecutar_orquestar_practica(
        evento="PEDIR_PISTA",
        estado_practica=estado,
        exploracion=exploracion,
        evento_id="ev-pista-1",
        adaptador=adaptador,
    )
    assert res_pista.ok
    # Solo se llamó 1 vez a preparar-actividad y 1 vez a dar-pista (nunca a evaluar-respuesta)
    operaciones_llamadas = [c["tipo_operacion"] for c in adaptador.llamadas]
    assert operaciones_llamadas == [
        "tutor_preparar_actividad_gemini",
        "tutor_dar_pista_gemini",
    ]

    # Cero respuestas enviadas, 1 pista registrada y recuadro resaltado
    assert estado.turnos_consumidos == 0
    assert estado.pistas_totales == 1
    assert len(estado.pistas_actividad_actual) == 1
    assert estado.pistas_actividad_actual[0].origen == "SOLICITUD_ALUMNO"
    assert estado.objeto_resaltado_id == str(obj_mug.objeto_id)
    assert estado.estado == "ESPERANDO_RESPUESTA"

    # Verificar el registro observable requerido para la defensa
    ultimo_registro = estado.traza_observable[-1]
    assert ultimo_registro.evento_usuario == "PEDIR_PISTA"
    assert ultimo_registro.skill_ejecutada == "dar-pista"
    assert ultimo_registro.decision_politica == "AUTORIZADA"
    assert ultimo_registro.conteo_respuestas == 0
    assert ultimo_registro.conteo_pistas == 1
    assert (
        ultimo_registro.resumen_observable
        == "Alumno pidió ayuda antes de responder → orquestar-practica autorizó dar-pista → pista presentada → cero respuestas enviadas"
    )


# ==========================================
# 3. Respuesta correcta y avance
# ==========================================


def test_respuesta_correcta_permite_avanzar_a_siguiente_actividad():
    """El alumno responde bien, evaluar-respuesta devuelve CORRECTA y el tutor permite avanzar."""
    exploracion = _crear_exploracion_prueba(2)
    obj_1, obj_2 = exploracion.objetos[0], exploracion.objetos[1]

    def resolvedor(tipo_operacion: str, esquema: Any) -> Resultado[Any]:
        if tipo_operacion == "tutor_preparar_actividad_gemini":
            conteo_prep = sum(1 for c in adaptador.llamadas if c["tipo_operacion"] == "tutor_preparar_actividad_gemini")
            obj_target = obj_1 if conteo_prep == 1 else obj_2
            return Resultado.exito(
                EsquemaActividadTutorIA(
                    consigna=f"¿Cómo se dice «{obj_target.nombre_es}» en inglés?",
                    objeto_ids_elegidos=[str(obj_target.objeto_id)],
                    objeto_objetivo_id=str(obj_target.objeto_id),
                    criterio_correccion="Coincidencia con el nombre del objeto.",
                    respuestas_aceptadas=[obj_target.nombre_en],
                    es_refuerzo=False,
                )
            )
        if tipo_operacion == "tutor_evaluar_respuesta_gemini":
            return Resultado.exito(
                EsquemaEvaluacionTutorIA(
                    valoracion="CORRECTA",
                    devolucion="¡Excelente! 'coffee mug' es exactamente la taza de café.",
                    dificultad_detectada=None,
                    objeto_confundido_id=None,
                )
            )
        if tipo_operacion == "tutor_orquestar_decision_gemini":
            return Resultado.exito(
                EsquemaDecisionOrquestadorIA(
                    accion_siguiente="AVANZAR",
                    motivo="El alumno respondió correctamente.",
                    mensaje_transicion="¡Muy bien! Puedes avanzar al siguiente objeto de la foto.",
                )
            )
        raise AssertionError(f"Operación inesperada: {tipo_operacion}")

    adaptador = AdaptadorGeminiTutorSimulado(resolvedor=resolvedor)
    estado = EstadoPracticaTutor(exploracion_id=str(exploracion.exploracion_id))
    mod_orq = cargar_ejecutor_skill("orquestar-practica")

    mod_orq.ejecutar_orquestar_practica(
        evento="INICIAR_PRACTICA",
        estado_practica=estado,
        exploracion=exploracion,
        adaptador=adaptador,
    )
    assert estado.actividad_actual is not None
    assert estado.actividad_actual.objeto_ids == [str(obj_1.objeto_id)]

    # El alumno envía una respuesta correcta
    res_envio = mod_orq.ejecutar_orquestar_practica(
        evento="ENVIAR_RESPUESTA",
        estado_practica=estado,
        exploracion=exploracion,
        respuesta_alumno="coffee mug",
        adaptador=adaptador,
    )
    assert res_envio.ok
    assert estado.turnos_consumidos == 1
    assert estado.ultima_evaluacion is not None
    assert estado.ultima_evaluacion.valoracion == "CORRECTA"
    assert estado.ultima_accion_pedagogica == "AVANZAR"
    assert str(obj_1.objeto_id) in estado.objetos_practicados_ids

    # El alumno avanza a la siguiente actividad
    res_avance = mod_orq.ejecutar_orquestar_practica(
        evento="AVANZAR_ACTIVIDAD",
        estado_practica=estado,
        exploracion=exploracion,
        adaptador=adaptador,
    )
    assert res_avance.ok
    assert estado.actividad_actual is not None
    assert estado.actividad_actual.objeto_ids == [str(obj_2.objeto_id)]
    assert estado.estado == "ESPERANDO_RESPUESTA"


# ==========================================
# 4. Respuesta incorrecta -> Pista o Refuerzo
# ==========================================


def test_respuesta_incorrecta_ofrece_pista_o_prepara_refuerzo_contrastivo():
    """Cuando el alumno se equivoca, el tutor puede ofrecer una pista (OFRECER_PISTA)
    o preparar un ejercicio de refuerzo contrastivo (PREPARAR_REFUERZO) si confundió dos objetos.
    """
    exploracion = _crear_exploracion_prueba(2)
    obj_mug, obj_chair = exploracion.objetos[0], exploracion.objetos[1]

    # Escenario A: Respuesta incorrecta -> el tutor decide OFRECER_PISTA
    def resolvedor_pista(tipo_operacion: str, esquema: Any) -> Resultado[Any]:
        if tipo_operacion == "tutor_preparar_actividad_gemini":
            return Resultado.exito(
                EsquemaActividadTutorIA(
                    consigna="¿Cómo se nombra el objeto #1 en inglés?",
                    objeto_ids_elegidos=[str(obj_mug.objeto_id)],
                    objeto_objetivo_id=str(obj_mug.objeto_id),
                    criterio_correccion="Exact match.",
                    respuestas_aceptadas=["coffee mug"],
                    es_refuerzo=False,
                )
            )
        if tipo_operacion == "tutor_evaluar_respuesta_gemini":
            return Resultado.exito(
                EsquemaEvaluacionTutorIA(
                    valoracion="INCORRECTA",
                    devolucion="Esa palabra no corresponde a la taza de café.",
                    dificultad_detectada="vocabulario_no_reconocido",
                    objeto_confundido_id=None,
                )
            )
        if tipo_operacion == "tutor_orquestar_decision_gemini":
            return Resultado.exito(
                EsquemaDecisionOrquestadorIA(
                    accion_siguiente="OFRECER_PISTA",
                    motivo="Ayudar con una pista inicial.",
                    mensaje_transicion="Te dejo una pista para ayudarte a identificarlo.",
                )
            )
        if tipo_operacion == "tutor_dar_pista_gemini":
            return Resultado.exito(
                EsquemaPistaTutorIA(
                    texto_pista="Observa el objeto #1: sirve para tomar café caliente.",
                    objeto_resaltado_id=str(obj_mug.objeto_id),
                )
            )
        raise AssertionError(f"Operación inesperada: {tipo_operacion}")

    adaptador_a = AdaptadorGeminiTutorSimulado(resolvedor=resolvedor_pista)
    estado_a = EstadoPracticaTutor(exploracion_id=str(exploracion.exploracion_id))
    mod_orq = cargar_ejecutor_skill("orquestar-practica")

    mod_orq.ejecutar_orquestar_practica("INICIAR_PRACTICA", estado_a, exploracion, adaptador=adaptador_a)
    res_a = mod_orq.ejecutar_orquestar_practica(
        "ENVIAR_RESPUESTA",
        estado_a,
        exploracion,
        respuesta_alumno="table",
        adaptador=adaptador_a,
    )
    assert res_a.ok
    assert estado_a.turnos_consumidos == 1
    assert estado_a.ultima_accion_pedagogica == "OFRECER_PISTA"
    assert estado_a.pistas_totales == 1
    assert estado_a.pistas_actividad_actual[-1].origen == "DECISION_TUTOR"
    assert estado_a.objeto_resaltado_id == str(obj_mug.objeto_id)

    # Escenario B: El alumno confunde coffee mug con wooden chair -> PREPARAR_REFUERZO
    def resolvedor_refuerzo(tipo_operacion: str, esquema: Any) -> Resultado[Any]:
        if tipo_operacion == "tutor_preparar_actividad_gemini":
            llamadas_prep = sum(1 for c in adaptador_b.llamadas if c["tipo_operacion"] == "tutor_preparar_actividad_gemini")
            if llamadas_prep == 1:
                return Resultado.exito(
                    EsquemaActividadTutorIA(
                        consigna="¿Cómo se dice «taza de café» (#1) en inglés?",
                        objeto_ids_elegidos=[str(obj_mug.objeto_id)],
                        objeto_objetivo_id=str(obj_mug.objeto_id),
                        criterio_correccion="Exact match.",
                        respuestas_aceptadas=["coffee mug"],
                        es_refuerzo=False,
                    )
                )
            return Resultado.exito(
                EsquemaActividadTutorIA(
                    consigna="Refuerzo: 'wooden chair' es la silla de madera (#2). ¿Cómo se escribe en inglés la taza de café (#1)?",
                    objeto_ids_elegidos=[str(obj_mug.objeto_id), str(obj_chair.objeto_id)],
                    objeto_objetivo_id=str(obj_mug.objeto_id),
                    criterio_correccion="Distinguir coffee mug de wooden chair.",
                    respuestas_aceptadas=["coffee mug"],
                    es_refuerzo=True,
                )
            )
        if tipo_operacion == "tutor_evaluar_respuesta_gemini":
            return Resultado.exito(
                EsquemaEvaluacionTutorIA(
                    valoracion="INCORRECTA",
                    devolucion="Escribiste 'wooden chair', que corresponde a la silla de madera (#2), no a la taza de café (#1).",
                    dificultad_detectada="confusion_entre_objetos_de_la_foto",
                    objeto_confundido_id=str(obj_chair.objeto_id),
                )
            )
        if tipo_operacion == "tutor_orquestar_decision_gemini":
            return Resultado.exito(
                EsquemaDecisionOrquestadorIA(
                    accion_siguiente="PREPARAR_REFUERZO",
                    motivo="El alumno confundió dos objetos de la foto.",
                    mensaje_transicion="Vamos a realizar un ejercicio breve para diferenciar ambos objetos de la foto.",
                )
            )
        raise AssertionError(f"Operación inesperada: {tipo_operacion}")

    adaptador_b = AdaptadorGeminiTutorSimulado(resolvedor=resolvedor_refuerzo)
    estado_b = EstadoPracticaTutor(exploracion_id=str(exploracion.exploracion_id))

    mod_orq.ejecutar_orquestar_practica("INICIAR_PRACTICA", estado_b, exploracion, adaptador=adaptador_b)
    res_b = mod_orq.ejecutar_orquestar_practica(
        "ENVIAR_RESPUESTA",
        estado_b,
        exploracion,
        respuesta_alumno="wooden chair",
        adaptador=adaptador_b,
    )
    assert res_b.ok
    assert estado_b.ultima_accion_pedagogica == "PREPARAR_REFUERZO"
    assert estado_b.refuerzos_realizados == 1
    assert estado_b.actividad_actual is not None
    assert estado_b.actividad_actual.es_refuerzo is True
    assert set(estado_b.actividad_actual.objeto_ids) == {str(obj_mug.objeto_id), str(obj_chair.objeto_id)}


# ==========================================
# 5. Foto con un solo objeto, IDs ajenos y límites de policy.json
# ==========================================


def test_practica_con_un_solo_objeto_y_bloqueos_de_politica():
    """La práctica funciona con un solo objeto en la foto, y bloquea IDs ajenos o excesos de policy.json."""
    exploracion_1 = _crear_exploracion_prueba(1)
    unico_obj = exploracion_1.objetos[0]

    # 5.1 Funciona con 1 solo objeto
    estado_1 = EstadoPracticaTutor(exploracion_id=str(exploracion_1.exploracion_id))
    mod_orq = cargar_ejecutor_skill("orquestar-practica")
    res_1 = mod_orq.ejecutar_orquestar_practica("INICIAR_PRACTICA", estado_1, exploracion_1)
    assert res_1.ok
    assert estado_1.actividad_actual is not None
    assert estado_1.actividad_actual.objeto_ids == [str(unico_obj.objeto_id)]

    # 5.2 Bloquea si una skill devuelve un objeto_id que no pertenece a la foto activa
    res_val = validar_ids_pertenecen_a_foto(["id-ajeno-inexistente"], exploracion_1.objetos)
    assert not res_val.ok
    assert res_val.error is not None
    assert res_val.error.codigo == CODIGO_ACCESO_DENEGADO

    id_inventado = str(uuid4())

    def resolvedor_id_ajeno(tipo_operacion: str, esquema: Any) -> Resultado[Any]:
        return Resultado.exito(
            EsquemaActividadTutorIA(
                consigna="Consigna con ID inventado fuera de la foto.",
                objeto_ids_elegidos=[id_inventado],
                objeto_objetivo_id=id_inventado,
                criterio_correccion="Criterio",
                respuestas_aceptadas=["fake"],
                es_refuerzo=False,
            )
        )

    adaptador_ajeno = AdaptadorGeminiTutorSimulado(resolvedor=resolvedor_id_ajeno)
    estado_ajeno = EstadoPracticaTutor(exploracion_id=str(exploracion_1.exploracion_id))
    res_ajeno = mod_orq.ejecutar_orquestar_practica(
        "INICIAR_PRACTICA",
        estado_ajeno,
        exploracion_1,
        adaptador=adaptador_ajeno,
    )
    assert not res_ajeno.ok
    assert res_ajeno.error is not None
    assert res_ajeno.error.codigo == CODIGO_ACCESO_DENEGADO
    assert estado_ajeno.traza_observable[-1].decision_politica == "BLOQUEADA"

    # 5.3 Bloquea cuando se supera el límite de pistas por actividad en policy.json
    policy_estricta = cargar_politica_tutor()
    policy_estricta["limits"]["max_pistas_por_actividad"] = 1

    res_p1 = mod_orq.ejecutar_orquestar_practica(
        "PEDIR_PISTA",
        estado_1,
        exploracion_1,
        policy_override=policy_estricta,
    )
    assert res_p1.ok
    assert estado_1.pistas_totales == 1

    # Segunda pista en la misma actividad queda bloqueada por policy.json
    res_p2 = mod_orq.ejecutar_orquestar_practica(
        "PEDIR_PISTA",
        estado_1,
        exploracion_1,
        policy_override=policy_estricta,
    )
    assert not res_p2.ok
    assert res_p2.error is not None
    assert res_p2.error.codigo == CODIGO_LIMITE_ALCANZADO
    assert estado_1.pistas_totales == 1
    assert estado_1.traza_observable[-1].decision_politica == "BLOQUEADA"


# ==========================================
# 6. Idempotencia en reruns de Streamlit, reintento tras fallo y retorno a exploración
# ==========================================


def test_idempotencia_rerun_reintento_sin_duplicar_y_cierre():
    """Un rerun con el mismo evento_id no duplica llamadas ni consume turnos;
    un fallo permite reintentar sin duplicar el intento; y al cerrar se vuelve a la foto.
    """
    exploracion = _crear_exploracion_prueba(2)
    estado = EstadoPracticaTutor(exploracion_id=str(exploracion.exploracion_id))
    mod_orq = cargar_ejecutor_skill("orquestar-practica")

    mod_orq.ejecutar_orquestar_practica("INICIAR_PRACTICA", estado, exploracion, evento_id="ev-init")
    assert len(estado.traza_observable) == 1

    # Rerun con el mismo evento_id no vuelve a ejecutar la skill ni agrega trazas duplicadas
    mod_orq.ejecutar_orquestar_practica("INICIAR_PRACTICA", estado, exploracion, evento_id="ev-init")
    assert len(estado.traza_observable) == 1

    # Simulamos un fallo transitorio de Gemini al enviar respuesta
    fallar = {"activo": True}

    def resolvedor_con_fallo(tipo_operacion: str, esquema: Any) -> Resultado[Any]:
        if fallar["activo"]:
            return Resultado.fallo(
                codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                mensaje_usuario="Tiempo de espera agotado al contactar a Gemini.",
                reintentable=True,
            )
        if tipo_operacion == "tutor_evaluar_respuesta_gemini":
            return Resultado.exito(
                EsquemaEvaluacionTutorIA(
                    valoracion="CORRECTA",
                    devolucion="¡Correcto!",
                    dificultad_detectada=None,
                    objeto_confundido_id=None,
                )
            )
        return Resultado.exito(
            EsquemaDecisionOrquestadorIA(
                accion_siguiente="AVANZAR",
                motivo="Correcta",
                mensaje_transicion="Avanzamos.",
            )
        )

    adaptador = AdaptadorGeminiTutorSimulado(resolvedor=resolvedor_con_fallo)
    res_fallo = mod_orq.ejecutar_orquestar_practica(
        "ENVIAR_RESPUESTA",
        estado,
        exploracion,
        respuesta_alumno="coffee mug",
        evento_id="ev-resp-fallida",
        adaptador=adaptador,
    )
    assert not res_fallo.ok
    # El fallo NO consumió turno
    assert estado.turnos_consumidos == 0

    # Reintentamos cuando el servicio se recupera
    fallar["activo"] = False
    res_reintento = mod_orq.ejecutar_orquestar_practica(
        "ENVIAR_RESPUESTA",
        estado,
        exploracion,
        respuesta_alumno="coffee mug",
        evento_id="ev-resp-reintento",
        adaptador=adaptador,
    )
    assert res_reintento.ok
    assert estado.turnos_consumidos == 1

    # Cerrar práctica finaliza el estado y conserva intacta la exploración
    res_cierre = mod_orq.ejecutar_orquestar_practica(
        "CERRAR_PRACTICA",
        estado,
        exploracion,
        evento_id="ev-cierre",
    )
    assert res_cierre.ok
    assert estado.estado == "FINALIZADA"


def test_integracion_ui_streamlit_activar_pista_y_volver_a_foto():
    """Verifica con AppTest de Streamlit la activación opcional del tutor,
    el botón «Dame una pista» y el botón «Volver a explorar la foto».
    """
    exploracion = _crear_exploracion_prueba(2)
    obj_1 = exploracion.objetos[0]

    def resolvedor_ui(tipo_operacion: str, esquema: Any) -> Resultado[Any]:
        if tipo_operacion == "tutor_preparar_actividad_gemini":
            return Resultado.exito(
                EsquemaActividadTutorIA(
                    consigna="Write the English name of object #1.",
                    objeto_ids_elegidos=[str(obj_1.objeto_id)],
                    objeto_objetivo_id=str(obj_1.objeto_id),
                    criterio_correccion="Exact match.",
                    respuestas_aceptadas=[obj_1.nombre_en],
                    es_refuerzo=False,
                )
            )
        if tipo_operacion == "tutor_dar_pista_gemini":
            return Resultado.exito(
                EsquemaPistaTutorIA(
                    texto_pista="Hint from UI test: it is a mug for coffee.",
                    objeto_resaltado_id=str(obj_1.objeto_id),
                )
            )
        raise AssertionError(f"Operación inesperada en UI: {tipo_operacion}")

    adaptador_ui = AdaptadorGeminiTutorSimulado(resolvedor=resolvedor_ui)

    def script_app():
        import streamlit as st
        from homelens.ui.estado import inicializar_estado_sesion
        from homelens.ui.tutor import renderizar_seccion_tutor_en_exploracion

        inicializar_estado_sesion()
        exp = st.session_state["exploracion_actual"]
        renderizar_seccion_tutor_en_exploracion(exp)

    at = AppTest.from_function(script_app)
    at.session_state["exploracion_actual"] = exploracion
    at.session_state["_tutor_adaptador_override"] = adaptador_ui
    at.run(timeout=15)

    assert not at.exception
    # Antes de tocar «Practicar con el tutor», no hubo llamadas a Gemini
    assert at.session_state["tutor_activo"] is False
    assert len(adaptador_ui.llamadas) == 0

    # El usuario toca «Practicar con el tutor»
    at.button(key="btn_practicar_con_tutor").click().run(timeout=15)
    assert not at.exception
    assert at.session_state["tutor_activo"] is True
    assert len(adaptador_ui.llamadas) == 1

    # El usuario toca «Dame una pista» antes de responder
    at.button(key="btn_tutor_pedir_pista").click().run(timeout=15)
    assert not at.exception
    estado_sesion: EstadoPracticaTutor = at.session_state["tutor_estado"]
    assert estado_sesion.turnos_consumidos == 0
    assert estado_sesion.pistas_totales == 1
    assert at.session_state["objeto_seleccionado_id"] == obj_1.objeto_id

    # El usuario toca «Volver a explorar la foto»
    at.button(key="btn_tutor_volver_foto").click().run(timeout=15)
    assert not at.exception
    assert at.session_state["tutor_activo"] is False
    assert at.session_state["exploracion_actual"].exploracion_id == exploracion.exploracion_id
    assert at.session_state["objeto_seleccionado_id"] is None


def test_regresion_mostrar_exploracion_completa_selector_tutor_pista_y_volver(monkeypatch):
    """Prueba de regresión con la vista de exploración completa (`mostrar_exploracion`):
    dibuja primero el selector `selector_objeto_activo_<id>`, activa el tutor, pide una pista
    antes de responder y vuelve a explorar la foto sin lanzar StreamlitWidgetAlreadyInstantiatedError.
    Verifica además que la selección manual desde las tarjetas sigue funcionando.
    """
    import streamlit as st

    # AppTest de esta versión de Streamlit no serializa opciones con emoji en segmented_control
    monkeypatch.setattr(
        st,
        "segmented_control",
        lambda *a, **kw: st.radio(*a, horizontal=True, **kw),
        raising=False,
    )
    exploracion = _crear_exploracion_prueba(2)
    obj_1, obj_2 = exploracion.objetos[0], exploracion.objetos[1]
    key_selector = f"selector_objeto_activo_{exploracion.exploracion_id}"
    key_pendiente = f"_pendiente_selector_objeto_activo_{exploracion.exploracion_id}"

    def resolvedor_ui(tipo_operacion: str, esquema: Any) -> Resultado[Any]:
        if tipo_operacion == "tutor_preparar_actividad_gemini":
            return Resultado.exito(
                EsquemaActividadTutorIA(
                    consigna="¿Cómo se escribe en inglés el objeto #1?",
                    objeto_ids_elegidos=[str(obj_1.objeto_id)],
                    objeto_objetivo_id=str(obj_1.objeto_id),
                    criterio_correccion="Exact match.",
                    respuestas_aceptadas=[obj_1.nombre_en],
                    es_refuerzo=False,
                )
            )
        if tipo_operacion == "tutor_dar_pista_gemini":
            return Resultado.exito(
                EsquemaPistaTutorIA(
                    texto_pista="Pista: observa la taza de café (#1).",
                    objeto_resaltado_id=str(obj_1.objeto_id),
                )
            )
        raise AssertionError(f"Operación inesperada en UI completa: {tipo_operacion}")

    adaptador_ui = AdaptadorGeminiTutorSimulado(resolvedor=resolvedor_ui)

    def script_exploracion_completa():
        import streamlit as st
        from homelens.ui.estado import inicializar_estado_sesion
        from homelens.ui.exploracion import mostrar_exploracion

        inicializar_estado_sesion()
        exp = st.session_state["exploracion_actual"]
        mostrar_exploracion(exp, imagen=None)

    at = AppTest.from_function(script_exploracion_completa)
    at.session_state["exploracion_actual"] = exploracion
    at.session_state["_tutor_adaptador_override"] = adaptador_ui

    # 1. Primer renderizado de la vista de exploración completa (crea el selector primero)
    at.run(timeout=15)
    assert not at.exception
    assert at.session_state[key_selector] == "👁️ Ver todos"
    assert len(adaptador_ui.llamadas) == 0

    # 2. Activar «Practicar con el tutor» después de haberse dibujado el selector
    at.button(key="btn_practicar_con_tutor").click().run(timeout=15)
    assert not at.exception
    assert at.session_state["tutor_activo"] is True
    assert at.session_state["objeto_seleccionado_id"] == obj_1.objeto_id
    assert at.session_state[key_selector] == f"#1 — {obj_1.nombre_en} / {obj_1.nombre_es}"
    assert key_pendiente not in at.session_state
    assert len(adaptador_ui.llamadas) == 1

    # 3. Pedir una pista antes de responder («Dame una pista»)
    at.button(key="btn_tutor_pedir_pista").click().run(timeout=15)
    assert not at.exception
    estado_sesion: EstadoPracticaTutor = at.session_state["tutor_estado"]
    assert estado_sesion.turnos_consumidos == 0
    assert estado_sesion.pistas_totales == 1
    assert len(estado_sesion.pistas_actividad_actual) == 1
    assert at.session_state["objeto_seleccionado_id"] == obj_1.objeto_id
    assert at.session_state[key_selector] == f"#1 — {obj_1.nombre_en} / {obj_1.nombre_es}"
    assert key_pendiente not in at.session_state
    # El redibujado tras pedir pista NO duplicó la llamada al modelo (1 preparar + 1 pista = 2)
    assert [c["tipo_operacion"] for c in adaptador_ui.llamadas] == [
        "tutor_preparar_actividad_gemini",
        "tutor_dar_pista_gemini",
    ]

    # 4. Un redibujado adicional (enfocar manualmente desde las tarjetas y desde el selector) funciona sin duplicar pista ni llamadas
    at.button(key=f"btn_focus_{obj_2.objeto_id}").click().run(timeout=15)
    assert not at.exception
    assert at.session_state["objeto_seleccionado_id"] == obj_2.objeto_id
    assert at.session_state[key_selector] == f"#2 — {obj_2.nombre_en} / {obj_2.nombre_es}"
    assert estado_sesion.turnos_consumidos == 0
    assert estado_sesion.pistas_totales == 1
    assert len(adaptador_ui.llamadas) == 2

    at.radio(key=key_selector).set_value(f"#1 — {obj_1.nombre_en} / {obj_1.nombre_es}").run(timeout=15)
    assert not at.exception
    assert at.session_state["objeto_seleccionado_id"] == obj_1.objeto_id
    assert at.session_state[key_selector] == f"#1 — {obj_1.nombre_en} / {obj_1.nombre_es}"
    assert estado_sesion.turnos_consumidos == 0
    assert estado_sesion.pistas_totales == 1
    assert len(adaptador_ui.llamadas) == 2

    # 5. Volver a explorar la foto desde el tutor restaura «Ver todos» sin excepción
    at.button(key="btn_tutor_volver_foto").click().run(timeout=15)
    assert not at.exception
    assert at.session_state["tutor_activo"] is False
    assert at.session_state["objeto_seleccionado_id"] is None
    assert at.session_state[key_selector] == "👁️ Ver todos"
    assert key_pendiente not in at.session_state
    assert len(adaptador_ui.llamadas) == 2

