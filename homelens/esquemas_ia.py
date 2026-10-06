"""Esquemas de validación para las respuestas de modelos de IA (Gemini).

Separados de los modelos del dominio y de persistencia.
Compatibles con la serialización Schema de google.generativeai (sin 'default', 'minimum', 'maximum').
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class RecuadroIA(BaseModel):
    """Coordenadas de recuadro retornadas por el modelo (0-1000)."""
    ymin: int
    xmin: int
    ymax: int
    xmax: int


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
    estado: str
    objetos: List[ObjetoIA]
    actividades: List[ActividadIA]


class RespuestaFindItIA(BaseModel):
    """Estructura de verificación para el desafío Find It."""
    estado: str
    mensaje: str
    recuadro_encontrado: Optional[RecuadroIA]
