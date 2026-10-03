"""Pruebas para preparación y validación de imágenes."""

import io
import unittest
from PIL import Image
from homelens.imagenes import preparar_imagen, liberar_imagen
from homelens.errores import CODIGO_IMAGEN_INVALIDA


class TestImagenes(unittest.TestCase):

    def test_preparar_imagen_valida_png(self):
        buf = io.BytesIO()
        img = Image.new("RGB", (300, 200), color="blue")
        img.save(buf, format="PNG")
        contenido = buf.getvalue()

        res = preparar_imagen(contenido)
        self.assertTrue(res.ok)
        self.assertIsNotNone(res.valor)
        self.assertEqual(res.valor.mime_type, "image/png")
        self.assertEqual(res.valor.ancho, 300)
        self.assertEqual(res.valor.alto, 200)

    def test_preparar_imagen_bytes_vacios(self):
        res = preparar_imagen(b"")
        self.assertFalse(res.ok)
        self.assertIsNotNone(res.error)
        self.assertEqual(res.error.codigo, CODIGO_IMAGEN_INVALIDA)

    def test_preparar_imagen_excede_limite(self):
        buf = io.BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(buf, format="JPEG")
        contenido = buf.getvalue()

        res = preparar_imagen(contenido, max_bytes=10)
        self.assertFalse(res.ok)
        self.assertIsNotNone(res.error)
        self.assertEqual(res.error.codigo, CODIGO_IMAGEN_INVALIDA)

    def test_liberar_imagen(self):
        liberar_imagen(b"dummy")
        liberar_imagen(None)


if __name__ == "__main__":
    unittest.main()
