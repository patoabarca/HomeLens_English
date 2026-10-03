"""Módulo M6: Prácticas, cuestionarios y desafíos Find It."""

from __future__ import annotations
from typing import Optional
from uuid import UUID, uuid4

from homelens.errores import Resultado, CODIGO_RESPUESTA_INVALIDA
from homelens.modelos import (
    ContextoUsuario,
    ActividadPublica,
    ResultadoPractica,
    DesafioFindIt,
    ImagenPreparada,
    ResultadoIntento,
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
