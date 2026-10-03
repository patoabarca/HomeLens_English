"""Módulo M3: Análisis visual y educativo con Gemini."""

from __future__ import annotations
from uuid import UUID, uuid4
from datetime import datetime, timezone

from homelens.errores import Resultado, CODIGO_SERVICIO_NO_DISPONIBLE
from homelens.modelos import (
    ContextoUsuario,
    ImagenPreparada,
    Exploracion,
    DesafioFindIt,
    VerificacionFindIt,
    EstadoFindIt,
    EstadoAnalisis,
)


def analizar_exploracion(
    usuario: ContextoUsuario,
    imagen: ImagenPreparada,
    operacion_id: UUID,
) -> Resultado[Exploracion]:
    """Analiza una imagen mediante Gemini y genera objetos educativos y preguntas."""
    # Nota: M3 conectará con la integración en el Paso 3.
    return Resultado.fallo(
        codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
        mensaje_usuario="El servicio de análisis con Gemini se activará en el Paso 3 del desarrollo.",
        operacion_id=operacion_id,
    )


def verificar_find_it(
    usuario: ContextoUsuario,
    imagen: ImagenPreparada,
    desafio: DesafioFindIt,
    operacion_id: UUID,
) -> Resultado[VerificacionFindIt]:
    """Verifica si la imagen contiene el objeto del desafío Find It."""
    return Resultado.fallo(
        codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
        mensaje_usuario="La verificación de Find It se integrará en el Paso 3.",
        operacion_id=operacion_id,
    )
