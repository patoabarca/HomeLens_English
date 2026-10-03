"""Módulo M2: Captura y preparación de imágenes.

Implementa la validación de formato real (JPEG y PNG), comprobación de límites
de tamaño, corrección de orientación por EXIF, saneamiento de metadatos y
gestión de imágenes temporales en memoria para HomeLens English.
"""

from __future__ import annotations
import io
from typing import Any, Optional
from PIL import Image, ImageOps

from homelens.errores import Resultado, CODIGO_IMAGEN_INVALIDA
from homelens.modelos import ImagenPreparada

LIMITE_TAMANIO_BYTES_POR_DEFECTO = 10_000_000  # 10 MB (10 000 000 bytes)


def preparar_imagen(
    contenido: bytes,
    max_bytes: int = LIMITE_TAMANIO_BYTES_POR_DEFECTO,
    max_dimension_px: Optional[int] = None,
) -> Resultado[ImagenPreparada]:
    """Valida, decodifica, normaliza y prepara una imagen en memoria.

    Reglas de procesamiento:
    1. Comprueba el tamaño en bytes del archivo original antes de decodificar.
    2. Admite exclusivamente formatos reales JPEG y PNG.
    3. Verifica que la imagen sea íntegra y pueda decodificarse completamente.
    4. Corrige automáticamente la orientación según metadatos EXIF.
    5. Elimina metadatos innecesarios (GPS, datos de dispositivo) al generar la copia limpia.
    6. Normaliza modos de color (CMYK, P, L) a RGB/RGBA y compone transparencias en blanco para JPEG.
    7. Ajusta dimensiones preservando la proporción únicamente si se especifica max_dimension_px.
    8. Retorna ImagenPreparada con bytes limpios, MIME type y dimensiones finales coherentes.

    Args:
        contenido: Bytes crudos del archivo de imagen recibido.
        max_bytes: Límite máximo de tamaño admitido (por defecto 10 000 000 bytes).
        max_dimension_px: Dimensión máxima permitida (ancho o alto) en píxeles. Si es None,
                          se conservan las dimensiones originales.

    Returns:
        Resultado[ImagenPreparada]: Objeto con la imagen lista en memoria o error tipificado.
    """
    if not contenido:
        return Resultado.fallo(
            codigo=CODIGO_IMAGEN_INVALIDA,
            mensaje_usuario="No se ha recibido contenido de imagen.",
            reintentable=False,
        )

    # 1. Comprobar tamaño antes de decodificar
    if len(contenido) > max_bytes:
        limite_mb = max_bytes / 1_000_000
        return Resultado.fallo(
            codigo=CODIGO_IMAGEN_INVALIDA,
            mensaje_usuario=f"La imagen supera el límite permitido de {limite_mb:g} MB ({max_bytes} bytes).",
            reintentable=False,
        )

    try:
        # 2. Abrir y verificar integridad del archivo
        buffer_entrada = io.BytesIO(contenido)
        with Image.open(buffer_entrada) as img_raw:
            # Comprobar formato detectado por la cabecera real
            formato_origen = img_raw.format
            if formato_origen not in ("JPEG", "PNG", "MPO"):
                return Resultado.fallo(
                    codigo=CODIGO_IMAGEN_INVALIDA,
                    mensaje_usuario=f"Formato no admitido ('{formato_origen or 'desconocido'}'). Solo se admiten imágenes en formato JPEG y PNG.",
                    reintentable=False,
                )

            # Normalizar MPO (Multi-Picture Object de ciertas cámaras) a JPEG estándar
            formato_destino = "JPEG" if formato_origen in ("JPEG", "MPO") else "PNG"
            mime_type = "image/jpeg" if formato_destino == "JPEG" else "image/png"

            # 3. Decodificar completamente para detectar archivos truncados o dañados
            img_raw.load()

            # 4. Corregir orientación basada en EXIF
            try:
                img_orientada = ImageOps.exif_transpose(img_raw)
                if img_orientada is None:
                    img_orientada = img_raw.copy()
            except Exception:
                img_orientada = img_raw.copy()

            # 5. Normalización de modos de color y tratamiento de transparencia
            modo = img_orientada.mode
            if formato_destino == "JPEG":
                if modo in ("RGBA", "LA", "P"):
                    # Componer sobre fondo blanco para evitar artefactos negros en canales alfa
                    fondo = Image.new("RGB", img_orientada.size, (255, 255, 255))
                    img_rgba = img_orientada.convert("RGBA")
                    fondo.paste(img_rgba, mask=img_rgba.split()[3])
                    img_procesada = fondo
                elif modo != "RGB":
                    img_procesada = img_orientada.convert("RGB")
                else:
                    img_procesada = img_orientada.copy()
            else:
                # Formato PNG
                if modo in ("P", "LA"):
                    img_procesada = img_orientada.convert("RGBA")
                elif modo not in ("RGB", "RGBA"):
                    img_procesada = img_orientada.convert("RGB")
                else:
                    img_procesada = img_orientada.copy()

            # 6. Ajuste opcional de dimensiones manteniendo proporción
            if max_dimension_px is not None and max_dimension_px > 0:
                ancho_actual, alto_actual = img_procesada.size
                if ancho_actual > max_dimension_px or alto_actual > max_dimension_px:
                    img_procesada.thumbnail(
                        (max_dimension_px, max_dimension_px),
                        Image.Resampling.LANCZOS,
                    )

            ancho_final, alto_final = img_procesada.size
            if ancho_final <= 0 or alto_final <= 0:
                return Resultado.fallo(
                    codigo=CODIGO_IMAGEN_INVALIDA,
                    mensaje_usuario="Las dimensiones de la imagen procesada son inválidas.",
                    reintentable=False,
                )

            # 7. Serializar a bytes limpios sin metadatos EXIF residuales
            buffer_salida = io.BytesIO()
            if formato_destino == "JPEG":
                img_procesada.save(
                    buffer_salida,
                    format="JPEG",
                    quality=90,
                    optimize=True,
                )
            else:
                img_procesada.save(
                    buffer_salida,
                    format="PNG",
                    optimize=True,
                )

            bytes_limpios = buffer_salida.getvalue()

            preparada = ImagenPreparada(
                contenido=bytes_limpios,
                mime_type=mime_type,
                ancho=ancho_final,
                alto=alto_final,
            )
            return Resultado.exito(preparada)

    except Exception:
        return Resultado.fallo(
            codigo=CODIGO_IMAGEN_INVALIDA,
            mensaje_usuario="El archivo no pudo ser decodificado como una imagen válida o está corrupto.",
            reintentable=False,
        )


def liberar_imagen(estado_imagen: Optional[Any]) -> None:
    """Libera referencias y recursos en memoria asociados a la imagen temporal.

    Args:
        estado_imagen: Objeto o contenedor de imagen a descartar.
    """
    if estado_imagen is not None:
        try:
            if hasattr(estado_imagen, "close") and callable(estado_imagen.close):
                estado_imagen.close()
            del estado_imagen
        except Exception:
            pass
