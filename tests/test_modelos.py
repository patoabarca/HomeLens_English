"""Pruebas para modelos de dominio, validaciones e invariantes."""

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from homelens.errores import Resultado, ErrorOperacion, CODIGO_IMAGEN_INVALIDA
from homelens.modelos import (
    ContextoUsuario,
    RecuadroNormalizado,
    Opcion,
    Actividad,
    Exploracion,
    EstadoAnalisis,
)


class TestModelosDominio(unittest.TestCase):

    def test_resultado_exito(self):
        res = Resultado.exito("datos_correctos")
        self.assertTrue(res.ok)
        self.assertEqual(res.valor, "datos_correctos")
        self.assertIsNone(res.error)

    def test_resultado_fallo(self):
        res = Resultado.fallo(codigo=CODIGO_IMAGEN_INVALIDA, mensaje_usuario="Imagen rota")
        self.assertFalse(res.ok)
        self.assertIsNone(res.valor)
        self.assertIsNotNone(res.error)
        self.assertEqual(res.error.codigo, CODIGO_IMAGEN_INVALIDA)

    def test_recuadro_normalizado_valido(self):
        rec = RecuadroNormalizado(ymin=100, xmin=200, ymax=600, xmax=700)
        self.assertEqual(rec.ymin, 100)
        self.assertEqual(rec.xmin, 200)
        self.assertEqual(rec.ymax, 600)
        self.assertEqual(rec.xmax, 700)

    def test_recuadro_normalizado_invalido_fuera_rango(self):
        with self.assertRaises(ValueError):
            RecuadroNormalizado(ymin=-10, xmin=0, ymax=500, xmax=500)

        with self.assertRaises(ValueError):
            RecuadroNormalizado(ymin=0, xmin=0, ymax=1001, xmax=500)

    def test_recuadro_normalizado_invalido_orden(self):
        with self.assertRaises(ValueError):
            RecuadroNormalizado(ymin=500, xmin=100, ymax=400, xmax=600)

    def test_actividad_valida(self):
        opciones = [
            Opcion(opcion_id="opt_1", texto="Desk"),
            Opcion(opcion_id="opt_2", texto="Chair"),
            Opcion(opcion_id="opt_3", texto="Window"),
        ]
        act = Actividad(
            actividad_id=uuid4(),
            exploracion_id=uuid4(),
            objeto_ids=[uuid4()],
            pregunta="What is this object?",
            opciones=opciones,
            opcion_correcta_id="opt_1",
            explicacion="It is a desk.",
        )
        self.assertEqual(len(act.opciones), 3)
        self.assertEqual(act.opcion_correcta_id, "opt_1")

    def test_actividad_invalida_numero_opciones(self):
        opciones = [
            Opcion(opcion_id="opt_1", texto="Desk"),
            Opcion(opcion_id="opt_2", texto="Chair"),
        ]
        with self.assertRaises(ValueError):
            Actividad(
                actividad_id=uuid4(),
                exploracion_id=uuid4(),
                objeto_ids=[uuid4()],
                pregunta="Question?",
                opciones=opciones,
                opcion_correcta_id="opt_1",
                explicacion="Explanation",
            )


if __name__ == "__main__":
    unittest.main()
