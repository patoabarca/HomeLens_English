"""Pruebas unitarias para el módulo M2 de preparación y validación de imágenes."""

import io
import unittest
from PIL import Image
from PIL.ExifTags import TAGS

from homelens.imagenes import preparar_imagen, liberar_imagen
from homelens.errores import CODIGO_IMAGEN_INVALIDA
from homelens.modelos import ImagenPreparada


class TestImagenes(unittest.TestCase):

    def _crear_imagen_bytes(
        self,
        formato: str = "PNG",
        dimensiones: tuple[int, int] = (300, 200),
        color: str = "blue",
        modo: str = "RGB",
        exif_dict: dict | None = None,
    ) -> bytes:
        """Crea sintéticamente una imagen en memoria para pruebas."""
        img = Image.new(modo, dimensiones, color=color)
        buf = io.BytesIO()
        if exif_dict and formato == "JPEG":
            exif = img.getexif()
            for k, v in exif_dict.items():
                exif[k] = v
            img.save(buf, format=formato, exif=exif)
        else:
            img.save(buf, format=formato)
        return buf.getvalue()

    def test_preparar_imagen_valida_png(self):
        contenido = self._crear_imagen_bytes(formato="PNG", dimensiones=(300, 200), color="green")
        res = preparar_imagen(contenido)

        self.assertTrue(res.ok)
        self.assertIsNotNone(res.valor)
        self.assertEqual(res.valor.mime_type, "image/png")
        self.assertEqual(res.valor.ancho, 300)
        self.assertEqual(res.valor.alto, 200)
        self.assertGreater(len(res.valor.contenido), 0)

    def test_preparar_imagen_valida_jpeg(self):
        contenido = self._crear_imagen_bytes(formato="JPEG", dimensiones=(400, 250), color="red")
        res = preparar_imagen(contenido)

        self.assertTrue(res.ok)
        self.assertIsNotNone(res.valor)
        self.assertEqual(res.valor.mime_type, "image/jpeg")
        self.assertEqual(res.valor.ancho, 400)
        self.assertEqual(res.valor.alto, 250)

    def test_preparar_imagen_bytes_vacios(self):
        res = preparar_imagen(b"")
        self.assertFalse(res.ok)
        self.assertIsNone(res.valor)
        self.assertIsNotNone(res.error)
        self.assertEqual(res.error.codigo, CODIGO_IMAGEN_INVALIDA)

    def test_preparar_imagen_excede_limite_bytes(self):
        contenido = self._crear_imagen_bytes(formato="JPEG", dimensiones=(100, 100))
        # Forzar un límite menor al tamaño de la imagen generada
        res = preparar_imagen(contenido, max_bytes=50)

        self.assertFalse(res.ok)
        self.assertIsNone(res.valor)
        self.assertIsNotNone(res.error)
        self.assertEqual(res.error.codigo, CODIGO_IMAGEN_INVALIDA)
        self.assertIn("supera el límite", res.error.mensaje_usuario)

    def test_preparar_imagen_formato_no_admitido_gif(self):
        contenido = self._crear_imagen_bytes(formato="GIF", dimensiones=(100, 100))
        res = preparar_imagen(contenido)

        self.assertFalse(res.ok)
        self.assertIsNone(res.valor)
        self.assertEqual(res.error.codigo, CODIGO_IMAGEN_INVALIDA)
        self.assertIn("Formato no admitido", res.error.mensaje_usuario)

    def test_preparar_imagen_formato_no_admitido_bmp(self):
        contenido = self._crear_imagen_bytes(formato="BMP", dimensiones=(100, 100))
        res = preparar_imagen(contenido)

        self.assertFalse(res.ok)
        self.assertEqual(res.error.codigo, CODIGO_IMAGEN_INVALIDA)

    def test_preparar_imagen_archivo_corrupto_o_texto_disfrazado(self):
        # Bytes de texto arbitrario que simulan un archivo corrupto
        contenido_falso = b"Esto no es una imagen real aunque se guarde como foto.jpg"
        res = preparar_imagen(contenido_falso)

        self.assertFalse(res.ok)
        self.assertIsNone(res.valor)
        self.assertEqual(res.error.codigo, CODIGO_IMAGEN_INVALIDA)

    def test_preparar_imagen_jpeg_truncado(self):
        # Tomar una imagen JPEG válida y truncar sus bytes a la mitad
        contenido_real = self._crear_imagen_bytes(formato="JPEG", dimensiones=(200, 200))
        contenido_truncado = contenido_real[:len(contenido_real) // 3]

        res = preparar_imagen(contenido_truncado)
        self.assertFalse(res.ok)
        self.assertEqual(res.error.codigo, CODIGO_IMAGEN_INVALIDA)

    def test_correccion_orientacion_exif(self):
        # 0x0112 es la etiqueta Orientation en EXIF (valor 6 = rotar 90 grados en sentido horario)
        # Una imagen original de 400x200 con orientación 6 debe resultar transpuesta a 200x400
        contenido_exif = self._crear_imagen_bytes(
            formato="JPEG",
            dimensiones=(400, 200),
            color="yellow",
            exif_dict={0x0112: 6},
        )
        res = preparar_imagen(contenido_exif)

        self.assertTrue(res.ok)
        self.assertIsNotNone(res.valor)
        self.assertEqual(res.valor.ancho, 200)
        self.assertEqual(res.valor.alto, 400)

    def test_tratamiento_transparencia_png_a_jpeg(self):
        # Imagen RGBA con transparencia convertida a JPEG (composición sobre blanco)
        contenido_rgba = self._crear_imagen_bytes(
            formato="PNG",
            dimensiones=(150, 150),
            color="purple",
            modo="RGBA",
        )
        res = preparar_imagen(contenido_rgba)
        self.assertTrue(res.ok)
        self.assertEqual(res.valor.mime_type, "image/png")

    def test_coherencia_contenido_y_dimensiones(self):
        contenido = self._crear_imagen_bytes(formato="PNG", dimensiones=(240, 180), color="cyan")
        res = preparar_imagen(contenido)

        self.assertTrue(res.ok)
        prep: ImagenPreparada = res.valor

        # Reabrir los bytes procesados con Pillow y comprobar coherencia estricta
        with Image.open(io.BytesIO(prep.contenido)) as img_verificada:
            self.assertEqual(img_verificada.size, (prep.ancho, prep.alto))
            self.assertEqual(img_verificada.format, "PNG")

    def test_redimensionado_opcional_con_max_dimension(self):
        # Imagen grande de 1000x500 con max_dimension_px=500 -> debe quedar en 500x250
        contenido = self._crear_imagen_bytes(formato="PNG", dimensiones=(1000, 500))
        res = preparar_imagen(contenido, max_dimension_px=500)

        self.assertTrue(res.ok)
        self.assertEqual(res.valor.ancho, 500)
        self.assertEqual(res.valor.alto, 250)

    def test_liberar_imagen(self):
        # Asegurar que liberar_imagen maneja objetos varios sin excepciones
        liberar_imagen(b"dummy_bytes")
        liberar_imagen(None)
        liberar_imagen(ImagenPreparada(contenido=b"x", mime_type="image/png", ancho=1, alto=1))


if __name__ == "__main__":
    unittest.main()
