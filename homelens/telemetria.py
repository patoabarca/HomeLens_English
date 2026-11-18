"""Módulo M0: Telemetría y registro de métricas técnicas.

Permite registrar eventos técnicos, consumo y tiempos de respuesta de forma
segura y aislada del historial pedagógico del estudiante.
"""

from __future__ import annotations
import logging
from typing import Optional, Any
from uuid import uuid4
from decimal import Decimal

from homelens.modelos import EventoTecnico, RegistroConsumoIA, ContextoUsuario
from homelens.costos import calcular_costo_gemini

logger = logging.getLogger("homelens.telemetria")


def registrar_evento(
    evento: EventoTecnico,
    repositorio: Optional[Any] = None,
    usuario: Optional[ContextoUsuario] = None,
) -> None:
    """Registra un evento técnico de ejecución o consumo y lo persiste si corresponde.

    Tolerante a fallos: un fallo al registrar o persistir métricas nunca interrumpe
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
        pass

    # Persistencia centralizada en Supabase para operaciones reales de Gemini
    if (
        repositorio is not None
        and usuario is not None
        and not getattr(usuario, "es_demo", False)
        and hasattr(repositorio, "registrar_consumo_gemini")
    ):
        try:
            # Extraer métricas de tokens reportadas
            uso = evento.uso_reportado or {}
            p_tokens = uso.get("prompt_token_count")
            c_tokens = uso.get("candidates_token_count")
            t_tokens = uso.get("thoughts_token_count")
            tot_tokens = uso.get("total_token_count")
            cache_tokens = uso.get("cached_content_token_count")

            modelo_usado = evento.modelo or "gemini-3.6-flash"

            calc = calcular_costo_gemini(
                modelo=modelo_usado,
                prompt_tokens=p_tokens,
                candidates_tokens=c_tokens,
                thoughts_tokens=t_tokens,
                cached_tokens=cache_tokens,
                total_tokens=tot_tokens,
                fecha=evento.fecha,
            )

            registro = RegistroConsumoIA(
                id=uuid4(),
                operacion_id=evento.operacion_id,
                user_id=usuario.user_id,
                fecha=evento.fecha,
                modelo=modelo_usado,
                estado=evento.estado,
                duracion_ms=evento.duracion_ms,
                numero_llamadas=evento.numero_llamadas,
                numero_reintentos=evento.numero_reintentos,
                codigo_error=evento.codigo_error,
                prompt_tokens=p_tokens,
                candidates_tokens=c_tokens,
                thoughts_tokens=t_tokens,
                total_tokens=tot_tokens,
                cached_tokens=cache_tokens,
                tarifa_version=calc.tarifa_version,
                costo_estimado=calc.costo_estimado,
                metadatos=calc.desglose,
            )

            repositorio.registrar_consumo_gemini(usuario, registro)
        except Exception as e:
            logger.warning("Fallo silencioso al persistir métricas de consumo en repositorio: %s", e)
