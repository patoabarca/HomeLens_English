"""Pruebas unitarias para el módulo de cálculo de costos de Gemini (homelens.costos)."""

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from homelens.costos import (
    obtener_tarifa,
    calcular_costo_gemini,
)


class TestCostosGemini(unittest.TestCase):
    """Verifica la precisión, tarifas oficiales y componente de salida (respuesta + razonamiento)."""

    def test_obtener_tarifa_vigente_2026(self) -> None:
        """Verifica tarifas oficiales vigentes hasta 31/12/2026 para gemini-3.6-flash."""
        fecha_2026 = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        tarifa = obtener_tarifa("gemini-3.6-flash", fecha=fecha_2026)

        self.assertIsNotNone(tarifa)
        self.assertEqual(tarifa.version, "gemini-3.6-flash-2026-v2")
        self.assertEqual(tarifa.costo_entrada_millon, Decimal("0.75"))
        self.assertEqual(tarifa.costo_salida_millon, Decimal("3.75"))
        # Tarifa corregida de lectura de caché: US$ 0.075 / 1M
        self.assertEqual(tarifa.costo_cache_millon, Decimal("0.075"))

    def test_obtener_tarifa_estandar_2027(self) -> None:
        """Verifica transición oficial a tarifas estándar a partir de 2027."""
        fecha_2027 = datetime(2027, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        tarifa = obtener_tarifa("gemini-3.6-flash", fecha=fecha_2027)

        self.assertIsNotNone(tarifa)
        self.assertEqual(tarifa.version, "gemini-3.6-flash-2027-v2")
        self.assertEqual(tarifa.costo_entrada_millon, Decimal("1.50"))
        self.assertEqual(tarifa.costo_salida_millon, Decimal("7.50"))
        # Tarifa corregida de lectura de caché: US$ 0.15 / 1M
        self.assertEqual(tarifa.costo_cache_millon, Decimal("0.15"))

    def test_compatibilidad_modelo_gemini_2_5_flash(self) -> None:
        """Verifica tarifas registradas para gemini-2.5-flash."""
        fecha_2026 = datetime(2026, 11, 17, tzinfo=timezone.utc)
        tarifa = obtener_tarifa("gemini-2.5-flash", fecha=fecha_2026)
        self.assertIsNotNone(tarifa)
        self.assertEqual(tarifa.costo_entrada_millon, Decimal("0.75"))
        self.assertEqual(tarifa.costo_cache_millon, Decimal("0.075"))

    def test_modelo_desconocido_retorna_none(self) -> None:
        """Un modelo no registrado retorna None y costo no disponible."""
        tarifa = obtener_tarifa("modelo-inexistente-xyz")
        self.assertIsNone(tarifa)

        res = calcular_costo_gemini("modelo-inexistente-xyz", 100, 100)
        self.assertIsNone(res.costo_estimado)
        self.assertFalse(res.metadatos_completos)

    def test_calculo_costo_componente_salida_con_razonamiento(self) -> None:
        """Verifica que el componente de salida sume candidates_token_count + thoughts_token_count."""
        fecha_2026 = datetime(2026, 11, 17, tzinfo=timezone.utc)
        # prompt: 1000 tokens std = 1000/1M * 0.75 = 0.000750 USD
        # candidates: 300 tokens
        # thoughts: 200 tokens
        # Salida total = 300 + 200 = 500 tokens * 3.75/1M = 0.001875 USD
        # Total = 0.000750 + 0.001875 = 0.002625 USD
        res = calcular_costo_gemini(
            modelo="gemini-3.6-flash",
            prompt_tokens=1000,
            candidates_tokens=300,
            thoughts_tokens=200,
            fecha=fecha_2026,
        )

        self.assertTrue(res.metadatos_completos)
        self.assertIsNotNone(res.costo_estimado)
        self.assertEqual(res.costo_estimado, Decimal("0.002625"))
        self.assertEqual(res.desglose["tokens_respuesta_generada"], 300)
        self.assertEqual(res.desglose["tokens_razonamiento"], 200)
        self.assertEqual(res.desglose["tokens_salida_facturables"], 500)
        self.assertEqual(res.desglose["costo_entrada_usd"], "0.000750")
        self.assertEqual(res.desglose["costo_salida_usd"], "0.001875")

    def test_descuento_por_tokens_en_cache_y_tarifa_correcta(self) -> None:
        """Verifica que los tokens en caché se facturen a US$ 0.075 / 1M y no se duplique entrada."""
        fecha_2026 = datetime(2026, 11, 17, tzinfo=timezone.utc)
        # 1000 prompt tokens totales, con 600 provenientes de lectura de caché:
        # Entrada std = 400 * 0.75 / 1M = 0.000300 USD
        # Caché lectura = 600 * 0.075 / 1M = 0.000045 USD
        # Salida (100 candidates + 0 thoughts) = 100 * 3.75 / 1M = 0.000375 USD
        # Total = 0.000300 + 0.000045 + 0.000375 = 0.000720 USD
        res = calcular_costo_gemini(
            modelo="gemini-3.6-flash",
            prompt_tokens=1000,
            candidates_tokens=100,
            cached_tokens=600,
            fecha=fecha_2026,
        )
        self.assertTrue(res.metadatos_completos)
        self.assertEqual(res.desglose["tokens_entrada_estandar"], 400)
        self.assertEqual(res.desglose["tokens_cache_lectura"], 600)
        self.assertEqual(res.costo_estimado, Decimal("0.000720"))
        self.assertEqual(res.desglose["costo_cache_lectura_usd"], "0.000045")

    def test_simulacion_usage_metadata_completa(self) -> None:
        """Prueba con estructura simulada equivalente a GenerateContentResponseUsageMetadata de Google."""
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 1500
        mock_usage.candidates_token_count = 450
        mock_usage.thoughts_token_count = 150
        mock_usage.total_token_count = 2100
        mock_usage.cached_content_token_count = 500

        fecha_2026 = datetime(2026, 11, 17, tzinfo=timezone.utc)
        # Entrada std: 1500 - 500 = 1000 * 0.75 / 1M = 0.000750 USD
        # Caché lectura: 500 * 0.075 / 1M = 0.0000375 -> 0.000038
        # Salida total: 450 + 150 = 600 * 3.75 / 1M = 0.002250 USD
        # Total esperado: 0.000750 + 0.0000375 + 0.002250 = 0.0030375 -> 0.003038 USD
        res = calcular_costo_gemini(
            modelo="gemini-3.6-flash",
            prompt_tokens=mock_usage.prompt_token_count,
            candidates_tokens=mock_usage.candidates_token_count,
            thoughts_tokens=mock_usage.thoughts_token_count,
            cached_tokens=mock_usage.cached_content_token_count,
            total_tokens=mock_usage.total_token_count,
            fecha=fecha_2026,
        )

        self.assertTrue(res.metadatos_completos)
        self.assertEqual(res.costo_estimado, Decimal("0.003038"))
        self.assertEqual(res.desglose["total_tokens_reportados"], 2100)
        self.assertEqual(res.desglose["total_tokens_calculados"], 2100)

    def test_valores_faltantes_declaran_costo_desconocido(self) -> None:
        """Cuando faltan tokens esenciales, el costo se declara None sin asumir cero."""
        res_sin_prompt = calcular_costo_gemini("gemini-3.6-flash", None, 100)
        self.assertIsNone(res_sin_prompt.costo_estimado)
        self.assertFalse(res_sin_prompt.metadatos_completos)

        res_sin_candidates = calcular_costo_gemini("gemini-3.6-flash", 100, None)
        self.assertIsNone(res_sin_candidates.costo_estimado)
        self.assertFalse(res_sin_candidates.metadatos_completos)


if __name__ == "__main__":
    unittest.main()
