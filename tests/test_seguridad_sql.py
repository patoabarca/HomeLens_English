"""Pruebas de validación estática y análisis de políticas RLS para Supabase.

Verifica la no-recursión en políticas RLS (evitando el error PostgreSQL 42P17),
los privilegios de mínimo acceso (GRANT/REVOKE) y la previsualización de datos simulados.
"""

from __future__ import annotations
import re
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from homelens.config import cargar_configuracion
from homelens.ui.consumo import generar_datos_simulados_consumo, calcular_resumen_consumo


RUTA_MIGRACION = Path(__file__).resolve().parent.parent / "sql" / "migracion_tarea_consumo_ia.sql"


class TestSeguridadSQL(unittest.TestCase):
    """Análisis estático de la migración SQL y políticas de Row Level Security."""

    def setUp(self) -> None:
        self.assertTrue(RUTA_MIGRACION.exists(), f"No se encontró el archivo de migración en {RUTA_MIGRACION}")
        self.sql_contenido = RUTA_MIGRACION.read_text(encoding="utf-8")

    def test_politica_creadores_autorizados_no_es_recursiva(self) -> None:
        """Comprueba que la política SELECT de creadores_autorizados no contenga subconsultas a sí misma.

        Previene el error de PostgreSQL '42P17: infinite recursion detected in policy for relation'.
        """
        # Extraer la definición de la política SELECT sobre creadores_autorizados
        patron_politica = re.compile(
            r'CREATE\s+POLICY\s+"[^"]+"\s+ON\s+public\.creadores_autorizados\s+FOR\s+SELECT\s+TO\s+authenticated\s+USING\s*\((.*?)\);',
            re.IGNORECASE | re.DOTALL,
        )
        match = patron_politica.search(self.sql_contenido)
        self.assertIsNotNone(match, "No se encontró la política SELECT para creadores_autorizados en el SQL.")

        expresion_using = match.group(1).strip()

        # Debe utilizar exactamente user_id = (SELECT auth.uid()) sin subconsultas a public.creadores_autorizados
        self.assertIn("user_id = (SELECT auth.uid())", expresion_using)
        self.assertNotIn("FROM public.creadores_autorizados", expresion_using)
        self.assertNotIn("FROM creadores_autorizados", expresion_using)

    def test_politica_insert_consumo_gemini_restringida_a_creadores(self) -> None:
        """Verifica que la política INSERT de consumo_gemini exija que el usuario pertenezca a creadores_autorizados."""
        patron_insert = re.compile(
            r'CREATE\s+POLICY\s+"[^"]+"\s+ON\s+public\.consumo_gemini\s+FOR\s+INSERT\s+TO\s+authenticated\s+WITH\s+CHECK\s*\((.*?)\);',
            re.IGNORECASE | re.DOTALL,
        )
        match = patron_insert.search(self.sql_contenido)
        self.assertIsNotNone(match, "No se encontró la política INSERT para consumo_gemini.")

        expresion_check = match.group(1).strip()
        # Debe exigir pertenencia a creadores_autorizados y coincidencia de auth.uid()
        self.assertIn("auth.uid()", expresion_check)
        self.assertIn("public.creadores_autorizados", expresion_check)

    def test_politica_select_consumo_gemini_restringida_a_creadores(self) -> None:
        """Verifica que la política SELECT de consumo_gemini esté restringida a los integrantes de creadores_autorizados."""
        patron_select = re.compile(
            r'CREATE\s+POLICY\s+"[^"]+"\s+ON\s+public\.consumo_gemini\s+FOR\s+SELECT\s+TO\s+authenticated\s+USING\s*\((.*?)\);',
            re.IGNORECASE | re.DOTALL,
        )
        match = patron_select.search(self.sql_contenido)
        self.assertIsNotNone(match, "No se encontró la política SELECT para consumo_gemini.")

        expresion_using = match.group(1).strip()
        self.assertIn("public.creadores_autorizados", expresion_using)

    def test_privilegios_minimos_grant_revoke(self) -> None:
        """Comprueba que no se otorgue INSERT/UPDATE/DELETE a usuarios autenticados sobre creadores_autorizados."""
        # creadores_autorizados: solo SELECT a authenticated
        self.assertIn("GRANT SELECT ON TABLE public.creadores_autorizados TO authenticated;", self.sql_contenido)
        self.assertNotIn("GRANT INSERT ON TABLE public.creadores_autorizados TO authenticated", self.sql_contenido)
        self.assertNotIn("GRANT UPDATE ON TABLE public.creadores_autorizados TO authenticated", self.sql_contenido)
        self.assertNotIn("GRANT DELETE ON TABLE public.creadores_autorizados TO authenticated", self.sql_contenido)

        # consumo_gemini: solo SELECT e INSERT a authenticated
        self.assertIn("GRANT SELECT, INSERT ON TABLE public.consumo_gemini TO authenticated;", self.sql_contenido)
        self.assertNotIn("GRANT UPDATE ON TABLE public.consumo_gemini", self.sql_contenido)
        self.assertNotIn("GRANT DELETE ON TABLE public.consumo_gemini", self.sql_contenido)

    def test_default_now_en_columnas_timestamptz(self) -> None:
        """Verifica que las columnas TIMESTAMPTZ utilicen DEFAULT now() en lugar de timezone('utc'::text, now())."""
        self.assertIn("creado_en TIMESTAMPTZ NOT NULL DEFAULT now()", self.sql_contenido)
        self.assertIn("fecha TIMESTAMPTZ NOT NULL DEFAULT now()", self.sql_contenido)
        self.assertNotIn("timezone('utc'::text, now())", self.sql_contenido)

    def test_restricciones_integridad_y_limpieza_metadatos(self) -> None:
        """Comprueba las restricciones CHECK para costos no negativos, consistencia de llamadas y metadatos sin secretos."""
        self.assertIn("chk_consumo_costo_no_negativo", self.sql_contenido)
        self.assertIn("costo_estimado IS NULL OR costo_estimado >= 0", self.sql_contenido)

        self.assertIn("chk_consumo_consistencia_llamadas_reintentos", self.sql_contenido)
        self.assertIn("numero_llamadas >= (numero_reintentos + 1)", self.sql_contenido)

        self.assertIn("chk_consumo_metadatos_sin_secretos", self.sql_contenido)
        self.assertIn("api_key", self.sql_contenido)

    def test_existencia_scripts_auxiliares_de_validacion_y_registro(self) -> None:
        """Verifica la presencia de los scripts SQL modulares de verificación RLS y registro de creadores."""
        ruta_registro = Path(__file__).resolve().parent.parent / "sql" / "procedimiento_registro_creadores.sql"
        ruta_verificacion = Path(__file__).resolve().parent.parent / "sql" / "verificar_seguridad_rls.sql"
        self.assertTrue(ruta_registro.exists(), "Falta el script sql/procedimiento_registro_creadores.sql")
        self.assertTrue(ruta_verificacion.exists(), "Falta el script sql/verificar_seguridad_rls.sql")


class TestPrevisualizacionDatosSimulados(unittest.TestCase):
    """Verifica la generación de datos simulados para previsualización local sin llamadas a APIs."""

    def test_generador_datos_simulados_retorna_registros_coherentes(self) -> None:
        """Comprueba que los datos simulados incluyan a los creadores de prueba, métricas y cálculo de costos."""
        with patch.dict(
            "os.environ",
            {
                "CREADOR_ID_PATRICIA": str(uuid4()),
                "CREADOR_ID_LUCAS": str(uuid4()),
                "CREADOR_ID_VICTORIA": str(uuid4()),
            },
        ):
            cfg_res = cargar_configuracion()
            self.assertTrue(cfg_res.ok)
            config = cfg_res.valor

            simulados = generar_datos_simulados_consumo(config)
            self.assertGreaterEqual(len(simulados), 10)

            # Comprobar que incluye a Patricia, Lucas y Victoria configurados para la prueba
            integrantes = {r.integrante_etiqueta for r in simulados}
            self.assertIn("Patricia", integrantes)
            self.assertIn("Lucas", integrantes)
            self.assertIn("Victoria", integrantes)

            # Comprobar cálculo de KPIs sobre datos simulados
            resumen = calcular_resumen_consumo(simulados)
            self.assertGreater(resumen.total_fotografias, 0)
            self.assertGreater(resumen.total_solicitudes, 0)
            self.assertGreater(resumen.total_tokens, 0)
            self.assertGreater(resumen.costo_acumulado, 0)
            self.assertIsNotNone(resumen.costo_promedio_por_foto)
            self.assertGreater(resumen.total_solicitudes_fallidas, 0)


if __name__ == "__main__":
    unittest.main()
