"""Módulo de cálculo de costos y tarifas de Gemini para HomeLens English.

Implementa el cálculo preciso de costos mediante Decimal para evitar imprecisiones
de punto flotante, con tarifas versionadas por modelo y fecha de vigencia.

Semántica de tokens de Google Gemini:
- prompt_token_count: Tokens totales de entrada (texto, imágenes, sistema).
- cached_content_token_count: Tokens de entrada leídos desde la caché de contexto.
  Para evitar cobro duplicado, los tokens leídos de caché se descuentan de los tokens
  de entrada estándar: tokens_entrada_std = max(0, prompt_tokens - cached_tokens).
- candidates_token_count: Tokens de respuesta generada por el modelo.
- thoughts_token_count: Tokens de razonamiento interno generados antes de la respuesta final.
- Componente de salida: candidates_token_count + thoughts_token_count (facturados a la tarifa de salida).
- total_token_count: Informativo oficial reportado por Gemini; se verifica para auditoría
  sin aplicarse como un cargo duplicado.

Almacenamiento de caché de contexto:
- Las llamadas de HomeLens English operan sobre imágenes individuales y prompts educativos
  sin sesiones de context caching persistentes con TTL horario.
- Cuando no se dispone de duración horaria de retención en los metadatos, el cargo de
  almacenamiento se declara no aplicable / no disponible.

Fuentes oficiales de tarifas (consultadas: 17/11/2026):
- Google AI Studio Pricing / Gemini API Docs: https://ai.google.dev/gemini-api/docs/pricing
Tarifas por millón de tokens para Gemini Flash (ej. gemini-3.6-flash / gemini-2.5-flash):
  * Vigencia hasta 31/12/2026:
      - Entrada estándar: US$ 0.75 por millón ($0.00000075 / token)
      - Salida (respuesta + razonamiento): US$ 3.75 por millón ($0.00000375 / token)
      - Lectura de caché de contexto: US$ 0.075 por millón ($0.000000075 / token)
  * Vigencia desde 01/01/2027:
      - Entrada estándar: US$ 1.50 por millón ($0.00000150 / token)
      - Salida (respuesta + razonamiento): US$ 7.50 por millón ($0.00000750 / token)
      - Lectura de caché de contexto: US$ 0.15 por millón ($0.00000015 / token)
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any


_UN_MILLON = Decimal("1000000")
_PRECISION_COSTO = Decimal("0.000001")  # 6 decimales para costos unitarios de llamadas


@dataclass(frozen=True)
class TarifaModelo:
    """Tarifa aplicable a un modelo de IA en un rango temporal específico."""
    modelo: str
    version: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime]
    costo_entrada_millon: Decimal
    costo_salida_millon: Decimal
    costo_cache_millon: Decimal


# Registro versionado de tarifas oficiales por modelo y fecha de vigencia
_TARIFAS_GEMINI: list[TarifaModelo] = [
    # Gemini 3.6 Flash / 2.5 Flash — Periodo hasta 31/12/2026
    TarifaModelo(
        modelo="gemini-3.6-flash",
        version="gemini-3.6-flash-2026-v2",
        fecha_inicio=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        fecha_fin=datetime(2026, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        costo_entrada_millon=Decimal("0.75"),
        costo_salida_millon=Decimal("3.75"),
        costo_cache_millon=Decimal("0.075"),
    ),
    # Gemini 3.6 Flash / 2.5 Flash — Periodo estándar desde 01/01/2027
    TarifaModelo(
        modelo="gemini-3.6-flash",
        version="gemini-3.6-flash-2027-v2",
        fecha_inicio=datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        fecha_fin=None,
        costo_entrada_millon=Decimal("1.50"),
        costo_salida_millon=Decimal("7.50"),
        costo_cache_millon=Decimal("0.15"),
    ),
    # Compatibilidad con gemini-2.5-flash
    TarifaModelo(
        modelo="gemini-2.5-flash",
        version="gemini-2.5-flash-2026-v2",
        fecha_inicio=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        fecha_fin=datetime(2026, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc),
        costo_entrada_millon=Decimal("0.75"),
        costo_salida_millon=Decimal("3.75"),
        costo_cache_millon=Decimal("0.075"),
    ),
    TarifaModelo(
        modelo="gemini-2.5-flash",
        version="gemini-2.5-flash-2027-v2",
        fecha_inicio=datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        fecha_fin=None,
        costo_entrada_millon=Decimal("1.50"),
        costo_salida_millon=Decimal("7.50"),
        costo_cache_millon=Decimal("0.15"),
    ),
]


def obtener_tarifa(modelo: str, fecha: Optional[datetime] = None) -> Optional[TarifaModelo]:
    """Busca la tarifa aplicable a un modelo en la fecha dada (UTC).

    Args:
        modelo: Identificador del modelo Gemini.
        fecha: Fecha y hora de la operación (si es naive, se asume UTC).

    Returns:
        TarifaModelo o None si el modelo no está registrado.
    """
    fecha_consulta = fecha if fecha is not None else datetime.now(timezone.utc)
    if fecha_consulta.tzinfo is None:
        fecha_consulta = fecha_consulta.replace(tzinfo=timezone.utc)

    modelo_norm = modelo.strip().lower()

    for t in _TARIFAS_GEMINI:
        if t.modelo.lower() == modelo_norm:
            if t.fecha_inicio <= fecha_consulta:
                if t.fecha_fin is None or fecha_consulta <= t.fecha_fin:
                    return t

    # Fallback por familia si el modelo es una variante de gemini flash
    if "flash" in modelo_norm:
        for t in _TARIFAS_GEMINI:
            if t.modelo == "gemini-3.6-flash":
                if t.fecha_inicio <= fecha_consulta:
                    if t.fecha_fin is None or fecha_consulta <= t.fecha_fin:
                        return t

    return None


@dataclass(frozen=True)
class ResultadoCalculoCosto:
    """Resultado del cálculo de costo estimado para una operación."""
    costo_estimado: Optional[Decimal]
    tarifa_version: str
    desglose: Dict[str, Any]
    metadatos_completos: bool


def calcular_costo_gemini(
    modelo: str,
    prompt_tokens: Optional[int],
    candidates_tokens: Optional[int],
    thoughts_tokens: Optional[int] = None,
    cached_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    fecha: Optional[datetime] = None,
) -> ResultadoCalculoCosto:
    """Calcula el costo estimado de una llamada a Gemini utilizando Decimal.

    Fórmula:
    - Componente entrada estándar: max(0, prompt_tokens - cached_tokens) * tarifa_entrada
    - Componente lectura de caché: cached_tokens * tarifa_cache_lectura
    - Componente salida: (candidates_tokens + (thoughts_tokens or 0)) * tarifa_salida
    - Costo total: componente entrada + componente caché + componente salida

    Si falta alguno de los tokens esenciales (prompt_tokens o candidates_tokens),
    el costo se declara desconocido (None) en lugar de asumir cero.

    Returns:
        ResultadoCalculoCosto con el costo en USD o None si faltan métricas.
    """
    tarifa = obtener_tarifa(modelo, fecha)
    if tarifa is None:
        return ResultadoCalculoCosto(
            costo_estimado=None,
            tarifa_version="tarifa_no_disponible",
            desglose={"error": f"Sin tarifa configurada para modelo '{modelo}'"},
            metadatos_completos=False,
        )

    # Si falta alguno de los tokens esenciales, el costo se declara desconocido
    if prompt_tokens is None or candidates_tokens is None:
        return ResultadoCalculoCosto(
            costo_estimado=None,
            tarifa_version=tarifa.version,
            desglose={"mensaje": "Métricas de tokens esenciales insuficientes para calcular costo."},
            metadatos_completos=False,
        )

    p_tokens = max(0, prompt_tokens)
    c_tokens = max(0, candidates_tokens)
    t_tokens = max(0, thoughts_tokens) if thoughts_tokens is not None else 0
    cache_tokens = max(0, cached_tokens) if cached_tokens is not None else 0

    # 1. Separar entrada estándar de entrada en caché para no cobrar dos veces
    tokens_entrada_estandar = max(0, p_tokens - cache_tokens)

    # 2. Componente de salida = candidates_token_count + thoughts_token_count
    tokens_salida_total = c_tokens + t_tokens

    # 3. Suma total calculada para contraste con total_token_count
    tokens_totales_calculados = tokens_entrada_estandar + cache_tokens + tokens_salida_total

    # 4. Cálculo monetario con Decimal
    costo_entrada_std = (Decimal(tokens_entrada_estandar) / _UN_MILLON) * tarifa.costo_entrada_millon
    costo_cache_lectura = (Decimal(cache_tokens) / _UN_MILLON) * tarifa.costo_cache_millon
    costo_salida = (Decimal(tokens_salida_total) / _UN_MILLON) * tarifa.costo_salida_millon

    costo_total = (costo_entrada_std + costo_cache_lectura + costo_salida).quantize(
        _PRECISION_COSTO, rounding=ROUND_HALF_UP
    )

    desglose = {
        "tarifa_version": tarifa.version,
        "tokens_entrada_estandar": tokens_entrada_estandar,
        "tokens_cache_lectura": cache_tokens,
        "tokens_respuesta_generada": c_tokens,
        "tokens_razonamiento": t_tokens,
        "tokens_salida_facturables": tokens_salida_total,
        "total_tokens_calculados": tokens_totales_calculados,
        "total_tokens_reportados": total_tokens,
        "costo_entrada_usd": str(costo_entrada_std.quantize(_PRECISION_COSTO)),
        "costo_cache_lectura_usd": str(costo_cache_lectura.quantize(_PRECISION_COSTO)),
        "costo_salida_usd": str(costo_salida.quantize(_PRECISION_COSTO)),
        "costo_almacenamiento_cache_usd": "no_aplicable",
        "costo_total_usd": str(costo_total),
    }

    return ResultadoCalculoCosto(
        costo_estimado=costo_total,
        tarifa_version=tarifa.version,
        desglose=desglose,
        metadatos_completos=True,
    )
