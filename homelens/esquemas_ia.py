"""Esquemas de validación para las respuestas de modelos de IA (Gemini).

Separados de los modelos del dominio y de persistencia.
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class RecuadroIA(BaseModel):
    """Coordenadas de recuadro retornadas por el modelo (0-1000)."""
    ymin: int = Field(ge=0, le=1000)
    xmin: int = Field(ge=0, le=1000)
    ymax: int = Field(ge=0, le=1000)
    xmax: int = Field(ge=0, le=1000)


class ObjetoIA(BaseModel):
    """Objeto educativo individual detectado por el modelo."""
    id_local: str
    nombre_en: str
    nombre_es: str
    recuadro: RecuadroIA
    frase_en: str
    frase_es: str


class OpcionIA(BaseModel):
    """Opción de actividad generada."""
    opcion_id: str
    texto: str


class ActividadIA(BaseModel):
    """Pregunta de práctica generada."""
    id_local: str
    objetos_relacionados: List[str]
    pregunta: str
    opciones: List[OpcionIA]
    opcion_correcta_id: str
    explicacion: str


class RespuestaExploracionIA(BaseModel):
    """Estructura completa de respuesta de análisis de imagen."""
    estado: str = Field(description="UTILIZABLE, SIN_OBJETOS_CLAROS o REPETIR_CAPTURA")
    objetos: List[ObjetoIA] = Field(default_factory=list)
    actividades: List[ActividadIA] = Field(default_factory=list)


class RespuestaFindItIA(BaseModel):
    """Estructura de verificación para el desafío Find It."""
    estado: str = Field(description="ENCONTRADO, NO_ENCONTRADO o INDETERMINABLE")
    mensaje: str
    recuadro_encontrado: Optional[RecuadroIA] = None
