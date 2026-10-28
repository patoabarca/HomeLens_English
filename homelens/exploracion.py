"""Módulo M4: Exploración, adaptación geométrica y tarjetas educativas.

Funciones puras para procesar coordenadas de recuadros, dibujar delimitadores
gráficos sobre imágenes en memoria y construir tarjetas pedagógicas para la
interfaz de usuario de HomeLens English.
"""

from __future__ import annotations
import io
from typing import List, Optional, Tuple
from uuid import UUID
from PIL import Image, ImageDraw, ImageFont

from homelens.modelos import (
    Exploracion,
    ImagenPreparada,
    ObjetoEducativo,
    RecuadroNormalizado,
    RecuadroPantalla,
    TarjetaObjeto,
)

# Paleta de contraste accesible para hasta 5 objetos reconocidos
PALETA_COLORES_OBJETOS = [
    {"borde": (0, 215, 255), "fondo": (0, 215, 255), "texto": (15, 23, 42)},    # #1 Cyan eléctrico
    {"borde": (251, 191, 36), "fondo": (251, 191, 36), "texto": (15, 23, 42)},  # #2 Ámbar dorado
    {"borde": (52, 211, 153), "fondo": (52, 211, 153), "texto": (15, 23, 42)},  # #3 Esmeralda menta
    {"borde": (244, 114, 182), "fondo": (244, 114, 182), "texto": (15, 23, 42)},# #4 Rosa fucsia
    {"borde": (167, 139, 250), "fondo": (167, 139, 250), "texto": (15, 23, 42)},# #5 Violeta
]


def adaptar_recuadro(
    recuadro: RecuadroNormalizado,
    ancho_visible: int,
    alto_visible: int,
) -> RecuadroPantalla:
    """Adapta un recuadro normalizado [0, 1000] a las dimensiones visibles en pantalla.

    Args:
        recuadro: Coordenadas normalizadas [ymin, xmin, ymax, xmax].
        ancho_visible: Ancho en píxeles del contenedor visible.
        alto_visible: Alto en píxeles del contenedor visible.

    Returns:
        RecuadroPantalla: Coordenadas escaladas para renderizado.
    """
    izquierda = (recuadro.xmin / 1000.0) * ancho_visible
    arriba = (recuadro.ymin / 1000.0) * alto_visible
    ancho = ((recuadro.xmax - recuadro.xmin) / 1000.0) * ancho_visible
    alto = ((recuadro.ymax - recuadro.ymin) / 1000.0) * alto_visible

    return RecuadroPantalla(
        izquierda=round(izquierda, 2),
        arriba=round(arriba, 2),
        ancho=round(ancho, 2),
        alto=round(alto, 2),
    )


def calcular_coordenadas_recuadro(
    recuadro: RecuadroNormalizado,
    ancho_imagen: int,
    alto_imagen: int,
) -> Tuple[int, int, int, int]:
    """Calcula las coordenadas enteras en píxeles [x0, y0, x1, y1] dentro de la imagen.

    Garantiza que los valores queden dentro de los límites reales de la imagen:
    - izquierda = xmin / 1000 * ancho
    - arriba = ymin / 1000 * alto
    - derecha = xmax / 1000 * ancho
    - abajo = ymax / 1000 * alto

    Args:
        recuadro: Coordenadas normalizadas en rango [0, 1000].
        ancho_imagen: Ancho real en píxeles de la imagen.
        alto_imagen: Alto real en píxeles de la imagen.

    Returns:
        Tuple[int, int, int, int]: (x0, y0, x1, y1) en píxeles.
    """
    x0 = int(round((recuadro.xmin / 1000.0) * ancho_imagen))
    y0 = int(round((recuadro.ymin / 1000.0) * alto_imagen))
    x1 = int(round((recuadro.xmax / 1000.0) * ancho_imagen))
    y1 = int(round((recuadro.ymax / 1000.0) * alto_imagen))

    # Asegurar que permanezcan dentro de los límites estrictos de la imagen
    x0 = max(0, min(ancho_imagen, x0))
    y0 = max(0, min(alto_imagen, y0))
    x1 = max(0, min(ancho_imagen, x1))
    y1 = max(0, min(alto_imagen, y1))

    # Evitar dimensiones colapsadas si xmin == xmax o ymin == ymax tras redondeo
    if x1 <= x0 and ancho_imagen > 0:
        x1 = min(ancho_imagen, x0 + 1)
    if y1 <= y0 and alto_imagen > 0:
        y1 = min(alto_imagen, y0 + 1)

    return x0, y0, x1, y1


def dibujar_recuadros(
    imagen: ImagenPreparada,
    objetos: List[ObjetoEducativo],
    objeto_seleccionado_id: Optional[UUID] = None,
) -> bytes:
    """Dibuja los recuadros delimitadores y etiquetas legibles sobre una copia de la imagen.

    Aplica las siguientes reglas de presentación:
    1. Utiliza exactamente la imagen preparada y orientada de la sesión sin recortes.
    2. Identifica cada objeto con su número (#1, #2...) y nombre en inglés.
    3. Si un objeto está seleccionado, destaca su recuadro con mayor grosor y sombreado
       y atenúa los no seleccionados para una clara diferenciación táctil y visual.
    4. Si ningún objeto está seleccionado, muestra todos los recuadros de forma destacada.
    5. Mantiene las etiquetas siempre dentro del área visible de la imagen.
    6. Retorna los bytes codificados en el formato de la imagen original (JPEG o PNG).

    Args:
        imagen: ImagenPreparada en memoria sobre la que se dibuja.
        objetos: Lista de objetos educativos reconocidos en la exploración.
        objeto_seleccionado_id: ID opcional del objeto enfocado.

    Returns:
        bytes: Bytes de la nueva imagen anotada lista para renderizar en la interfaz.
    """
    if not imagen or not imagen.contenido:
        return b""

    try:
        buffer_in = io.BytesIO(imagen.contenido)
        with Image.open(buffer_in) as img_base:
            ancho, alto = img_base.size

            # Crear imagen de trabajo en RGBA para soportar transparencias y destacados
            img_rgba = img_base.convert("RGBA")
            overlay = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            draw = ImageDraw.Draw(img_rgba)

            # Cálculo de tamaño de fuente dinámico y proporcionado a la resolución
            tamano_fuente = max(13, min(26, int(min(ancho, alto) * 0.024)))
            try:
                font = ImageFont.load_default(size=tamano_fuente)
            except Exception:
                font = ImageFont.load_default()

            hay_seleccion = objeto_seleccionado_id is not None

            if hay_seleccion:
                # Filtrar exclusivamente el objeto seleccionado usando str() para compatibilidad de tipos
                id_sel_str = str(objeto_seleccionado_id)
                objetos_a_dibujar = [
                    (idx, obj)
                    for idx, obj in enumerate(objetos)
                    if str(obj.objeto_id) == id_sel_str
                ]
            else:
                # Mostrar todos los objetos reconocidos
                objetos_a_dibujar = list(enumerate(objetos))

            for idx_orig, obj in objetos_a_dibujar:
                numero_objeto = idx_orig + 1
                color_info = PALETA_COLORES_OBJETOS[idx_orig % len(PALETA_COLORES_OBJETOS)]

                x0, y0, x1, y1 = calcular_coordenadas_recuadro(obj.recuadro, ancho, alto)

                # Definir grosores y estilos según selección
                if hay_seleccion:
                    # Borde claramente más grueso y sombreado translúcido interior para foco inequívoco
                    grosor = max(6, int(min(ancho, alto) * 0.012))
                    color_borde = color_info["borde"] + (255,)
                    fill_color = color_info["borde"] + (50,)
                    draw_overlay.rectangle([x0, y0, x1, y1], fill=fill_color)
                else:
                    grosor = max(3, int(min(ancho, alto) * 0.005))
                    color_borde = color_info["borde"] + (255,)

                # Dibujar borde exterior del recuadro
                draw.rectangle([x0, y0, x1, y1], outline=color_borde, width=grosor)

                # Texto de la etiqueta identificadora
                texto = f" #{numero_objeto} {obj.nombre_en} "

                # Medir dimensiones del texto para el contenedor de la etiqueta
                bbox = draw.textbbox((0, 0), texto, font=font)
                texto_w = bbox[2] - bbox[0]
                texto_h = bbox[3] - bbox[1]

                padding_x = 5
                padding_y = 4
                badge_w = texto_w + (padding_x * 2)
                badge_h = texto_h + (padding_y * 2)

                # Determinar posición vertical del badge:
                # Preferir justo arriba del recuadro; si no hay espacio, colocar justo dentro
                if y0 - badge_h >= 0:
                    badge_y0 = y0 - badge_h
                    badge_y1 = y0
                else:
                    badge_y0 = y0
                    badge_y1 = min(alto, y0 + badge_h)

                # Determinar posición horizontal del badge asegurando que no se corte
                badge_x0 = x0
                badge_x1 = x0 + badge_w
                if badge_x1 > ancho:
                    badge_x0 = max(0, ancho - badge_w)
                    badge_x1 = min(ancho, badge_x0 + badge_w)
                if badge_x0 < 0:
                    badge_x0 = 0
                    badge_x1 = min(ancho, badge_w)

                color_fondo_badge = color_info["fondo"] + (255,)
                color_texto_badge = color_info["texto"] + (255,)

                # Dibujar fondo de etiqueta y texto
                draw.rectangle([badge_x0, badge_y0, badge_x1, badge_y1], fill=color_fondo_badge)
                # Borde sutil al badge para máxima legibilidad
                draw.rectangle([badge_x0, badge_y0, badge_x1, badge_y1], outline=(0, 0, 0, 180), width=1)

                pos_x_texto = badge_x0 + padding_x
                pos_y_texto = badge_y0 + padding_y - bbox[1]
                draw.text((pos_x_texto, pos_y_texto), texto, fill=color_texto_badge, font=font)

            # Componer overlay translúcido sobre la imagen base
            img_final = Image.alpha_composite(img_rgba, overlay)

            # Serializar a bytes según el formato requerido
            buffer_out = io.BytesIO()
            if imagen.mime_type == "image/png":
                img_final.save(buffer_out, format="PNG")
            else:
                img_final.convert("RGB").save(buffer_out, format="JPEG", quality=90)

            return buffer_out.getvalue()

    except Exception:
        # En caso de excepción inesperada en el dibujado, devolver la imagen original
        return imagen.contenido


# Alias semántico documentado en especificaciones
generar_imagen_anotada = dibujar_recuadros


def construir_tarjetas(
    exploracion: Exploracion,
    ancho_visible: Optional[int] = None,
    alto_visible: Optional[int] = None,
) -> List[TarjetaObjeto]:
    """Construye la lista de tarjetas educativas a partir de los objetos de una exploración.

    Args:
        exploracion: Exploración válida con sus objetos detectados.
        ancho_visible: Ancho opcional del contenedor visible para calcular coordenadas de pantalla.
        alto_visible: Alto opcional del contenedor visible para calcular coordenadas de pantalla.

    Returns:
        List[TarjetaObjeto]: Lista de tarjetas pedagógicas listas para la vista.
    """
    tarjetas: List[TarjetaObjeto] = []
    for obj in exploracion.objetos:
        rec_pantalla: Optional[RecuadroPantalla] = None
        if ancho_visible is not None and alto_visible is not None:
            rec_pantalla = adaptar_recuadro(obj.recuadro, ancho_visible, alto_visible)

        tarjetas.append(
            TarjetaObjeto(
                objeto_id=obj.objeto_id,
                nombre_en=obj.nombre_en,
                nombre_es=obj.nombre_es,
                frase_en=obj.frase_en,
                frase_es=obj.frase_es,
                recuadro_pantalla=rec_pantalla,
            )
        )
    return tarjetas
