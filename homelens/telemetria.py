"""Módulo M0: Telemetría y registro de métricas técnicas.

Permite registrar eventos técnicos, consumo y tiempos de respuesta de forma
segura y aislada del historial pedagógico del estudiante.
"""

from __future__ import annotations
import logging
from homelens.modelos import EventoTecnico

logger = logging.getLogger("homelens.telemetria")


def registrar_evento(evento: EventoTecnico) -> None:
    """Registra un evento técnico de ejecución o consumo.
    
    Tolerante a fallos: un fallo al registrar métricas nunca interrumpe
    ni anula la experiencia educativa del usuario.
    """
    try:
        logger.info(
            "EventoTecnico | Op: %s | Tipo: %s | Duración: %sms | Estado: %s | Llamadas: %s | Reintentos: %s",
            evento.operacion_id,
            evento.tipo_operacion,
            evento.duracion_ms,
            evento.estado,
            evento.numero_llamadas,
            evento.numero_reintentos,
        )
    except Exception:
        # Fallo silencioso de telemetría para preservar el flujo principal
        pass
