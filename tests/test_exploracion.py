"""Pruebas para adaptación geométrica y tarjetas pedagógicas."""

import unittest
from datetime import datetime, timezone
from uuid import uuid4
from homelens.exploracion import adaptar_recuadro, construir_tarjetas
from homelens.modelos import (
    RecuadroNormalizado,
    Exploracion,
    ObjetoEducativo,
    EstadoAnalisis,
)


class TestExploracion(unittest.TestCase):

    def test_adaptar_recuadro(self):
        rec_norm = RecuadroNormalizado(ymin=100, xmin=200, ymax=600, xmax=700)
        rec_pantalla = adaptar_recuadro(rec_norm, ancho_visible=1000, alto_visible=800)

        self.assertEqual(rec_pantalla.izquierda, 200.0)
        self.assertEqual(rec_pantalla.arriba, 80.0)
        self.assertEqual(rec_pantalla.ancho, 500.0)
        self.assertEqual(rec_pantalla.alto, 400.0)

    def test_construir_tarjetas(self):
        exp_id = uuid4()
        obj1 = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=exp_id,
            nombre_en="Coffee Mug",
            nombre_es="Taza de café",
            recuadro=RecuadroNormalizado(ymin=100, xmin=100, ymax=300, xmax=300),
            frase_en="This is a coffee mug.",
            frase_es="Esta es una taza de café.",
        )
        exploracion = Exploracion(
            exploracion_id=exp_id,
            user_id=uuid4(),
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[obj1],
        )

        tarjetas = construir_tarjetas(exploracion)
        self.assertEqual(len(tarjetas), 1)
        self.assertEqual(tarjetas[0].nombre_en, "Coffee Mug")
        self.assertEqual(tarjetas[0].nombre_es, "Taza de café")


if __name__ == "__main__":
    unittest.main()
