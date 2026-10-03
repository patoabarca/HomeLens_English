"""Módulo M4: Exploración, adaptación geométrica y tarjetas educativas.

Funciones puras para procesar coordenadas de recuadros y construir tarjetas
pedagógicas para la interfaz de usuario.
"""

from __future__ import annotations
from typing import List

from homelens.modelos import (
    Exploracion,
    RecuadroNormalizado,
    RecuadroPantalla,
    TarjetaObjeto,
)


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


def construir_tarjetas(exploracion: Exploracion) -> List[TarjetaObjeto]:
    """Construye la lista de tarjetas educativas a partir de los objetos de una exploración.

    Args:
        exploracion: Exploración válida con sus objetos detectados.

    Returns:
        List[TarjetaObjeto]: Lista de tarjetas listas para la vista.
    """
    tarjetas: List[TarjetaObjeto] = []
    for obj in exploracion.objetos:
        tarjetas.append(
            TarjetaObjeto(
                objeto_id=obj.objeto_id,
                nombre_en=obj.nombre_en,
                nombre_es=obj.nombre_es,
                frase_en=obj.frase_en,
                frase_es=obj.frase_es,
            )
        )
    return tarjetas
