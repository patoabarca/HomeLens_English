"""Pruebas unitarias para adaptación geométrica, dibujado de recuadros y tarjetas pedagógicas."""

from __future__ import annotations
import io
import unittest
from datetime import datetime, timezone
from uuid import uuid4
from PIL import Image

from homelens.exploracion import (
    adaptar_recuadro,
    calcular_coordenadas_recuadro,
    dibujar_recuadros,
    construir_tarjetas,
    PALETA_COLORES_OBJETOS,
)
from homelens.modelos import (
    RecuadroNormalizado,
    Exploracion,
    ObjetoEducativo,
    EstadoAnalisis,
    ImagenPreparada,
)


def _crear_imagen_sintetica(ancho: int, alto: int, mime_type: str = "image/jpeg") -> ImagenPreparada:
    """Genera una imagen sintética limpia en memoria para pruebas geométricas."""
    img = Image.new("RGB", (ancho, alto), color=(180, 180, 180))
    buf = io.BytesIO()
    formato = "PNG" if mime_type == "image/png" else "JPEG"
    img.save(buf, format=formato)
    return ImagenPreparada(
        contenido=buf.getvalue(),
        mime_type=mime_type,
        ancho=ancho,
        alto=alto,
    )


class TestExploracion(unittest.TestCase):

    def test_adaptar_recuadro(self):
        """Comprueba la escala proporcional de coordenadas normalizadas a pantalla."""
        rec_norm = RecuadroNormalizado(ymin=100, xmin=200, ymax=600, xmax=700)
        rec_pantalla = adaptar_recuadro(rec_norm, ancho_visible=1000, alto_visible=800)

        self.assertEqual(rec_pantalla.izquierda, 200.0)
        self.assertEqual(rec_pantalla.arriba, 80.0)
        self.assertEqual(rec_pantalla.ancho, 500.0)
        self.assertEqual(rec_pantalla.alto, 400.0)

    def test_calcular_coordenadas_recuadro_horizontal(self):
        """Comprueba conversión geométrica en fotografía con orientación horizontal."""
        rec_norm = RecuadroNormalizado(ymin=150, xmin=250, ymax=750, xmax=850)
        ancho, alto = 1280, 720
        x0, y0, x1, y1 = calcular_coordenadas_recuadro(rec_norm, ancho, alto)

        self.assertEqual(x0, int(round(0.25 * 1280)))
        self.assertEqual(y0, int(round(0.15 * 720)))
        self.assertEqual(x1, int(round(0.85 * 1280)))
        self.assertEqual(y1, int(round(0.75 * 720)))

    def test_calcular_coordenadas_recuadro_vertical(self):
        """Comprueba conversión geométrica en fotografía vertical (ej. retrato de móvil)."""
        rec_norm = RecuadroNormalizado(ymin=100, xmin=200, ymax=900, xmax=800)
        ancho, alto = 720, 1280
        x0, y0, x1, y1 = calcular_coordenadas_recuadro(rec_norm, ancho, alto)

        self.assertEqual(x0, int(round(0.20 * 720)))
        self.assertEqual(y0, int(round(0.10 * 1280)))
        self.assertEqual(x1, int(round(0.80 * 720)))
        self.assertEqual(y1, int(round(0.90 * 1280)))

    def test_coordenadas_en_bordes_extremos(self):
        """Comprueba coordenadas en los límites exactos [0, 0, 1000, 1000]."""
        ancho, alto = 1000, 800
        rec_extremo = RecuadroNormalizado(ymin=0, xmin=0, ymax=1000, xmax=1000)
        x0, y0, x1, y1 = calcular_coordenadas_recuadro(rec_extremo, ancho, alto)

        self.assertEqual((x0, y0, x1, y1), (0, 0, 1000, 800))

        # Coordenada pegada a la esquina superior izquierda
        rec_top_left = RecuadroNormalizado(ymin=0, xmin=0, ymax=50, xmax=50)
        x0_tl, y0_tl, x1_tl, y1_tl = calcular_coordenadas_recuadro(rec_top_left, ancho, alto)
        self.assertEqual(x0_tl, 0)
        self.assertEqual(y0_tl, 0)
        self.assertGreater(x1_tl, 0)
        self.assertGreater(y1_tl, 0)

        # Coordenada pegada a la esquina inferior derecha
        rec_br = RecuadroNormalizado(ymin=950, xmin=950, ymax=1000, xmax=1000)
        x0_br, y0_br, x1_br, y1_br = calcular_coordenadas_recuadro(rec_br, ancho, alto)
        self.assertEqual(x1_br, 1000)
        self.assertEqual(y1_br, 800)

    def test_construir_tarjetas_correspondencia(self):
        """Comprueba correspondencia estable e íntegra entre objetos y tarjetas."""
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
        obj2 = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=exp_id,
            nombre_en="Wooden Desk",
            nombre_es="Escritorio de madera",
            recuadro=RecuadroNormalizado(ymin=400, xmin=100, ymax=800, xmax=900),
            frase_en="The notebook is on the wooden desk.",
            frase_es="El cuaderno está sobre el escritorio de madera.",
        )
        exploracion = Exploracion(
            exploracion_id=exp_id,
            user_id=uuid4(),
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[obj1, obj2],
        )

        tarjetas = construir_tarjetas(exploracion, ancho_visible=800, alto_visible=600)
        self.assertEqual(len(tarjetas), 2)

        # Verificar primer objeto
        self.assertEqual(tarjetas[0].objeto_id, obj1.objeto_id)
        self.assertEqual(tarjetas[0].nombre_en, "Coffee Mug")
        self.assertEqual(tarjetas[0].nombre_es, "Taza de café")
        self.assertEqual(tarjetas[0].frase_en, "This is a coffee mug.")
        self.assertEqual(tarjetas[0].frase_es, "Esta es una taza de café.")
        self.assertIsNotNone(tarjetas[0].recuadro_pantalla)
        self.assertEqual(tarjetas[0].recuadro_pantalla.izquierda, 80.0)

        # Verificar segundo objeto
        self.assertEqual(tarjetas[1].objeto_id, obj2.objeto_id)
        self.assertEqual(tarjetas[1].nombre_en, "Wooden Desk")

    def test_dibujar_recuadros_geometrica_sintetica(self):
        """Comprueba el dibujo in-memory de recuadros y etiquetas sobre imagen sintética."""
        imagen = _crear_imagen_sintetica(1280, 720)
        exp_id = uuid4()
        obj1 = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=exp_id,
            nombre_en="Lamp",
            nombre_es="Lámpara",
            recuadro=RecuadroNormalizado(ymin=50, xmin=50, ymax=400, xmax=350),
            frase_en="The lamp gives bright light.",
            frase_es="La lámpara da luz brillante.",
        )
        obj2 = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=exp_id,
            nombre_en="Chair",
            nombre_es="Silla",
            recuadro=RecuadroNormalizado(ymin=300, xmin=400, ymax=850, xmax=750),
            frase_en="Sit on this comfortable chair.",
            frase_es="Siéntate en esta cómoda silla.",
        )

        # Dibujar todos los recuadros
        bytes_todos = dibujar_recuadros(imagen, [obj1, obj2], objeto_seleccionado_id=None)
        self.assertTrue(len(bytes_todos) > 0)

        # Verificar que la imagen resultante sea decodificable y conserve dimensiones
        with Image.open(io.BytesIO(bytes_todos)) as img_out:
            self.assertEqual(img_out.size, (1280, 720))

    def test_dibujar_recuadros_con_seleccion_destacada(self):
        """Comprueba que seleccionar un objeto destaque su recuadro y no falle."""
        imagen = _crear_imagen_sintetica(800, 1000)
        exp_id = uuid4()
        obj_sel = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=exp_id,
            nombre_en="Notebook",
            nombre_es="Cuaderno",
            recuadro=RecuadroNormalizado(ymin=200, xmin=150, ymax=600, xmax=550),
            frase_en="Write notes in your notebook.",
            frase_es="Escribe notas en tu cuaderno.",
        )
        obj_otro = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=exp_id,
            nombre_en="Pen",
            nombre_es="Bolígrafo",
            recuadro=RecuadroNormalizado(ymin=650, xmin=200, ymax=850, xmax=400),
            frase_en="Use a blue pen.",
            frase_es="Usa un bolígrafo azul.",
        )

        # Destacar obj_sel
        bytes_destacado = dibujar_recuadros(
            imagen=imagen,
            objetos=[obj_sel, obj_otro],
            objeto_seleccionado_id=obj_sel.objeto_id,
        )
        self.assertTrue(len(bytes_destacado) > 0)

        with Image.open(io.BytesIO(bytes_destacado)) as img_out:
            self.assertEqual(img_out.size, (800, 1000))

    def test_dibujar_recuadros_oculta_otros_objetos_y_soporta_str(self):
        """Comprueba que al enfocar un objeto solo se dibuje ese objeto, y que soporte UUID y str."""
        imagen = _crear_imagen_sintetica(600, 600)
        exp_id = uuid4()
        id1 = uuid4()
        id2 = uuid4()
        obj1 = ObjetoEducativo(
            objeto_id=id1,
            exploracion_id=exp_id,
            nombre_en="Chair",
            nombre_es="Silla",
            recuadro=RecuadroNormalizado(ymin=100, xmin=100, ymax=400, xmax=400),
            frase_en="A chair.",
            frase_es="Una silla.",
        )
        obj2 = ObjetoEducativo(
            objeto_id=id2,
            exploracion_id=exp_id,
            nombre_en="Table",
            nombre_es="Mesa",
            recuadro=RecuadroNormalizado(ymin=500, xmin=500, ymax=800, xmax=800),
            frase_en="A table.",
            frase_es="Una mesa.",
        )

        # 1. Enfocar con objeto_id de tipo UUID
        bytes_uuid = dibujar_recuadros(imagen, [obj1, obj2], objeto_seleccionado_id=id1)
        self.assertTrue(len(bytes_uuid) > 0)

        # 2. Enfocar con objeto_id de tipo str
        bytes_str = dibujar_recuadros(imagen, [obj1, obj2], objeto_seleccionado_id=str(id1))
        self.assertTrue(len(bytes_str) > 0)
        # Ambas llamadas deben producir idéntica imagen
        self.assertEqual(bytes_uuid, bytes_str)

        # 3. Ver todos (None) restaura todos los recuadros
        bytes_todos = dibujar_recuadros(imagen, [obj1, obj2], objeto_seleccionado_id=None)
        self.assertTrue(len(bytes_todos) > 0)
        # La imagen con todos los objetos debe ser diferente a la imagen con solo uno
        self.assertNotEqual(bytes_uuid, bytes_todos)


if __name__ == "__main__":
    unittest.main()
