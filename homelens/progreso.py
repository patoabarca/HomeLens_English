"""Módulo M8: Consulta y cálculo del progreso pedagógico.

Funciones para consolidar palabras aprendidas y estadísticas de aciertos
a partir del vocabulario explorado y los intentos registrados.
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Dict

from homelens.modelos import (
    ObjetoEducativo,
    IntentoPractica,
    ResumenProgreso,
    PalabraResumen,
    EstadoPalabra,
    ResultadoIntento,
)


def calcular_progreso(
    vocabulario: List[ObjetoEducativo],
    intentos: List[IntentoPractica],
) -> ResumenProgreso:
    """Calcula el progreso formativo del estudiante de forma pura.

    - Agrupa palabras normalizadas.
    - Determina si están EXPLORADAS o PRACTICADAS según los intentos válidos.
    - Contabiliza resultados de cuestionarios y Find It.
    """
    # Mapeo de objetos practicados y última fecha
    objetos_practicados: Dict[str, datetime] = {}
    resultados_por_tipo = {
        "cuestionarios_correctos": 0,
        "cuestionarios_incorrectos": 0,
        "find_it_encontrados": 0,
        "find_it_no_encontrados": 0,
        "find_it_indeterminables": 0,
    }

    for intento in intentos:
        # Registrar aciertos/fallos según tipo
        if intento.tipo.value == "CUESTIONARIO":
            if intento.resultado == ResultadoIntento.CORRECTO:
                resultados_por_tipo["cuestionarios_correctos"] += 1
            elif intento.resultado == ResultadoIntento.INCORRECTO:
                resultados_por_tipo["cuestionarios_incorrectos"] += 1
        elif intento.tipo.value == "FIND_IT":
            if intento.resultado == ResultadoIntento.CORRECTO:
                resultados_por_tipo["find_it_encontrados"] += 1
            elif intento.resultado == ResultadoIntento.INCORRECTO:
                resultados_por_tipo["find_it_no_encontrados"] += 1
            elif intento.resultado == ResultadoIntento.INDETERMINABLE:
                resultados_por_tipo["find_it_indeterminables"] += 1

        # Si el intento fue evaluable, marcar los objetos relacionados como practicados
        if intento.resultado in (ResultadoIntento.CORRECTO, ResultadoIntento.INCORRECTO):
            for obj_id in intento.objeto_ids:
                str_id = str(obj_id)
                if str_id not in objetos_practicados or intento.fecha > objetos_practicados[str_id]:
                    objetos_practicados[str_id] = intento.fecha

    # Construir lista de palabras sin duplicados por nombre normalizado
    palabras_dict: Dict[str, PalabraResumen] = {}
    for obj in vocabulario:
        clave = obj.nombre_en.strip().lower()
        fue_practicada = str(obj.objeto_id) in objetos_practicados
        ultima_fecha = objetos_practicados.get(str(obj.objeto_id))

        if clave not in palabras_dict:
            palabras_dict[clave] = PalabraResumen(
                nombre_en=obj.nombre_en,
                nombre_es=obj.nombre_es,
                estado=EstadoPalabra.PRACTICADA if fue_practicada else EstadoPalabra.EXPLORADA,
                ultima_practica=ultima_fecha,
            )
        else:
            # Si ya existía pero esta instancia fue practicada, actualizar
            actual = palabras_dict[clave]
            if fue_practicada and actual.estado != EstadoPalabra.PRACTICADA:
                palabras_dict[clave] = PalabraResumen(
                    nombre_en=actual.nombre_en,
                    nombre_es=actual.nombre_es,
                    estado=EstadoPalabra.PRACTICADA,
                    ultima_practica=ultima_fecha,
                )

    return ResumenProgreso(
        palabras_exploradas=list(palabras_dict.values()),
        total_intentos=len(intentos),
        resultados_por_tipo=resultados_por_tipo,
    )
