"""Pruebas para cálculo del progreso del estudiante."""

import unittest
from datetime import datetime, timezone
from uuid import uuid4
from homelens.progreso import calcular_progreso
from homelens.modelos import (
    ObjetoEducativo,
    RecuadroNormalizado,
    IntentoPractica,
    TipoIntento,
    ResultadoIntento,
    EstadoPalabra,
)


class TestProgreso(unittest.TestCase):

    def test_calcular_progreso_vacio(self):
        resumen = calcular_progreso([], [])
        self.assertEqual(resumen.total_intentos, 0)
        self.assertEqual(len(resumen.palabras_exploradas), 0)

    def test_calcular_progreso_con_palabras_e_intentos(self):
        obj_id = uuid4()
        exp_id = uuid4()
        user_id = uuid4()

        obj = ObjetoEducativo(
            objeto_id=obj_id,
            exploracion_id=exp_id,
            nombre_en="Lamp",
            nombre_es="Lámpara",
            recuadro=RecuadroNormalizado(ymin=100, xmin=100, ymax=200, xmax=200),
            frase_en="The lamp is on the table.",
            frase_es="La lámpara está sobre la mesa.",
        )

        intento = IntentoPractica(
            intento_id=uuid4(),
            user_id=user_id,
            tipo=TipoIntento.CUESTIONARIO,
            fecha=datetime.now(timezone.utc),
            resultado=ResultadoIntento.CORRECTO,
            objeto_ids=[obj_id],
        )

        resumen = calcular_progreso([obj], [intento])
        self.assertEqual(resumen.total_intentos, 1)
        self.assertEqual(resumen.resultados_por_tipo["cuestionarios_correctos"], 1)
        self.assertEqual(len(resumen.palabras_exploradas), 1)
        self.assertEqual(resumen.palabras_exploradas[0].estado, EstadoPalabra.PRACTICADA)


if __name__ == "__main__":
    unittest.main()
