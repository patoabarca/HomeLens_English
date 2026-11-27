"""Módulo M6: Prácticas, cuestionarios y desafíos Find It."""

from __future__ import annotations
import random
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4, uuid5, NAMESPACE_DNS

from homelens.errores import (
    Resultado,
    CODIGO_RESPUESTA_INVALIDA,
    CODIGO_SESION_REQUERIDA,
)
from homelens.modelos import (
    ContextoUsuario,
    Actividad,
    ActividadPublica,
    Opcion,
    ResultadoPractica,
    DesafioFindIt,
    ImagenPreparada,
    ResultadoIntento,
    Exploracion,
    EstadoFindIt,
    VerificacionFindIt,
    IntentoPractica,
    TipoIntento,
)


def responder_actividad(
    usuario: ContextoUsuario,
    actividad_id: UUID,
    opcion_id: str,
    opcion_correcta_id: str,
    explicacion: str,
    intento_id: UUID,
) -> Resultado[ResultadoPractica]:
    """Evalúa la respuesta de una actividad pedagógica de forma local y pura."""
    es_correcta = (opcion_id.strip() == opcion_correcta_id.strip())
    resultado = ResultadoIntento.CORRECTO if es_correcta else ResultadoIntento.INCORRECTO

    return Resultado.exito(
        ResultadoPractica(
            intento_id=intento_id,
            resultado=resultado,
            explicacion=explicacion,
            registrado=False,
        )
    )


def obtener_actividad_publica(actividad: Actividad) -> ActividadPublica:
    """Extrae la proyección pública y segura de una actividad sin exponer la respuesta correcta ni la explicación."""
    return ActividadPublica(
        actividad_id=actividad.actividad_id,
        pregunta=actividad.pregunta,
        opciones=actividad.opciones,
    )


def mezclar_opciones_actividad(actividad: Actividad) -> list[Opcion]:
    """Genera una nueva lista con las 3 opciones en orden aleatorio, sin mutar la actividad original.

    Garantiza:
    1. Invarianza: La entidad original Actividad y su lista de opciones no son modificadas.
    2. Integridad: Se conservan exactamente las mismas 3 instancias de Opcion con sus opcion_id.
    3. Distribución variable: La opción correcta puede aparecer indistintamente en posición A, B o C.
    """
    return random.sample(actividad.opciones, len(actividad.opciones))


def validar_y_responder_actividad(
    usuario: ContextoUsuario,
    actividad: Actividad,
    opcion_id: str,
    intento_id: Optional[UUID] = None,
) -> Resultado[ResultadoPractica]:
    """Valida la opción elegida contra la actividad confiable del servidor y evalúa la respuesta.

    Reglas de dominio pedagógico:
    1. Verifica que exista un usuario autenticado legítimo.
    2. La actividad debe ser una instancia válida de Actividad.
    3. La opción seleccionada debe pertenecer estrictamente a una de las opciones legítimas de la actividad.
    4. La opción correcta y la explicación se obtienen directamente de la entidad Actividad del servidor,
       impidiendo cualquier manipulación externa.
    5. Invoca a responder_actividad() para la corrección local y determinista.
    """
    if usuario is None or not isinstance(usuario, ContextoUsuario):
        return Resultado.fallo(
            codigo=CODIGO_SESION_REQUERIDA,
            mensaje_usuario="Se requiere una sesión de usuario activa para responder cuestionarios.",
        )

    if actividad is None or not isinstance(actividad, Actividad):
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario="La actividad proporcionada no es válida.",
        )

    opcion_limpia = (opcion_id or "").strip()
    if not opcion_limpia:
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario="Debes seleccionar una opción antes de confirmar tu respuesta.",
        )

    ids_validos = {o.opcion_id.strip() for o in actividad.opciones}
    if opcion_limpia not in ids_validos:
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario="La opción seleccionada no pertenece a las opciones válidas de esta actividad.",
        )

    id_intento_efectivo = intento_id or uuid4()

    return responder_actividad(
        usuario=usuario,
        actividad_id=actividad.actividad_id,
        opcion_id=opcion_limpia,
        opcion_correcta_id=actividad.opcion_correcta_id,
        explicacion=actividad.explicacion,
        intento_id=id_intento_efectivo,
    )


_DESAFIOS_PREDETERMINADOS_FIND_IT: tuple[tuple[str, str], ...] = (
    ("Coffee Mug", "Taza de café"),
    ("Book", "Libro"),
    ("Chair", "Silla"),
    ("Lamp", "Lámpara"),
    ("Keys", "Llaves"),
    ("Spoon", "Cuchara"),
)


def obtener_desafios_find_it_disponibles(
    usuario: ContextoUsuario,
    exploracion_actual: Optional[Exploracion] = None,
) -> list[DesafioFindIt]:
    """Construye la lista de desafíos Find It disponibles para la sesión.

    Prioriza objetos descubiertos en la exploración activa y completa con
    vocabulario doméstico base usando UUIDs deterministas para estabilidad en UI.
    """
    ahora = datetime.now(timezone.utc)
    desafios: list[DesafioFindIt] = []
    vistos_en: set[str] = set()

    if exploracion_actual is not None and exploracion_actual.objetos:
        for obj in exploracion_actual.objetos:
            clave = obj.nombre_en.strip().lower()
            if not clave or clave in vistos_en:
                continue
            vistos_en.add(clave)
            desafios.append(
                DesafioFindIt(
                    desafio_id=uuid5(NAMESPACE_DNS, f"findit:{usuario.user_id}:{obj.objeto_id}"),
                    user_id=usuario.user_id,
                    objeto_origen_id=obj.objeto_id,
                    nombre_en=obj.nombre_en,
                    nombre_es=obj.nombre_es,
                    creado_en=exploracion_actual.creada_en,
                )
            )

    for nombre_en, nombre_es in _DESAFIOS_PREDETERMINADOS_FIND_IT:
        clave = nombre_en.strip().lower()
        if clave in vistos_en:
            continue
        vistos_en.add(clave)
        objeto_base_id = uuid5(NAMESPACE_DNS, f"homelens:objeto_base:{clave}")
        desafio_id = uuid5(NAMESPACE_DNS, f"homelens:findit:{usuario.user_id}:{clave}")
        desafios.append(
            DesafioFindIt(
                desafio_id=desafio_id,
                user_id=usuario.user_id,
                objeto_origen_id=objeto_base_id,
                nombre_en=nombre_en,
                nombre_es=nombre_es,
                creado_en=ahora,
            )
        )

    return desafios


def construir_intento_find_it(
    usuario: ContextoUsuario,
    desafio: DesafioFindIt,
    verificacion: VerificacionFindIt,
    intento_id: Optional[UUID] = None,
    fecha: Optional[datetime] = None,
) -> IntentoPractica:
    """Convierte el resultado de verificación Find It en un IntentoPractica listo para persistencia (Parte 10)."""
    mapa_resultados = {
        EstadoFindIt.ENCONTRADO: ResultadoIntento.CORRECTO,
        EstadoFindIt.NO_ENCONTRADO: ResultadoIntento.INCORRECTO,
        EstadoFindIt.INDETERMINABLE: ResultadoIntento.INDETERMINABLE,
    }
    return IntentoPractica(
        intento_id=intento_id or uuid4(),
        user_id=usuario.user_id,
        tipo=TipoIntento.FIND_IT,
        fecha=fecha or datetime.now(timezone.utc),
        desafio_id=desafio.desafio_id,
        resultado=mapa_resultados[verificacion.estado],
        objeto_ids=[desafio.objeto_origen_id],
    )
