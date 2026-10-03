"""Módulo M2: Captura y preparación de imágenes.

Valida formatos reales (JPEG, PNG), comprueba límites de tamaño y prepara
la estructura ImagenPreparada en memoria sin persistir fotografías.
"""

from __future__ import annotations
import io
from typing import Any, Optional
from PIL import Image

from homelens.errores import Resultado, CODIGO_IMAGEN_INVALIDA
from homelens.modelos import ImagenPreparada

MAX_SIZE_BYTES_DEFAULT = 10_000_000  # 10 MB


def preparar_imagen(
    contenido: bytes,
    max_bytes: int = MAX_SIZE_BYTES_DEFAULT,
) -> Resultado[ImagenPreparada]:
    """Valida los bytes de una imagen y prepara el contenedor en memoria.

    Args:
        contenido: Bytes crudos del archivo de imagen.
        max_bytes: Límite máximo de tamaño admitido en bytes.

    Returns:
        Resultado[ImagenPreparada]: Imagen validada o error descriptivo.
    """
    if not contenido:
        return Resultado.fallo(
            codigo=CODIGO_IMAGEN_INVALIDA,
            mensaje_usuario="No se ha recibido contenido de imagen.",
            reintentable=False,
        )

    if len(contenido) > max_bytes:
        return Resultado.fallo(
            codigo=CODIGO_IMAGEN_INVALIDA,
            mensaje_usuario=f"La imagen supera el límite permitido de {max_bytes // 1_000_000} MB.",
            reintentable=False,
        )

    try:
        # Validar formato y dimensiones reales usando Pillow
        with Image.open(io.BytesIO(contenido)) as img:
            formato = img.format
            if formato not in ("JPEG", "PNG"):
                return Resultado.fallo(
                    codigo=CODIGO_IMAGEN_INVALIDA,
                    mensaje_usuario="Formato no admitido. Solo se admiten imágenes JPEG y PNG.",
                    reintentable=False,
                )
            ancho, alto = img.size
            mime_type = "image/jpeg" if formato == "JPEG" else "image/png"

            if ancho <= 0 or alto <= 0:
                return Resultado.fallo(
                    codigo=CODIGO_IMAGEN_INVALIDA,
                    mensaje_usuario="Dimensiones de imagen inválidas.",
                    reintentable=False,
                )

            preparada = ImagenPreparada(
                contenido=contenido,
                mime_type=mime_type,
                ancho=ancho,
                alto=alto,
            )
            return Resultado.exito(preparada)

    except Exception:
        return Resultado.fallo(
            codigo=CODIGO_IMAGEN_INVALIDA,
            mensaje_usuario="El archivo no es una imagen válida o está dañado.",
            reintentable=False,
        )


def liberar_imagen(estado_imagen: Optional[Any]) -> None:
    """Elimina referencias temporales a la imagen en memoria para liberar recursos."""
    if estado_imagen is not None:
        try:
            del estado_imagen
        except Exception:
            pass
