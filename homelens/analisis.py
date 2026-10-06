"""Módulo M3: Análisis visual y educativo con Gemini.

Coordina la validación previa, la llamada multimodal mediante AdaptadorGemini,
la validación geométrica y pedagógica exhaustiva de la respuesta de IA, y la
traducción a las entidades inmutables del dominio (Exploracion, ObjetoEducativo, Actividad).
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Dict
from uuid import UUID, uuid4
from datetime import datetime, timezone

from homelens.config import cargar_configuracion
from homelens.errores import (
    Resultado,
    ErrorOperacion,
    CODIGO_RESPUESTA_INVALIDA,
    CODIGO_SERVICIO_NO_DISPONIBLE,
    CODIGO_IMAGEN_INVALIDA,
)
from homelens.esquemas_ia import RespuestaExploracionIA
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import (
    ContextoUsuario,
    ImagenPreparada,
    Exploracion,
    ObjetoEducativo,
    RecuadroNormalizado,
    Actividad,
    Opcion,
    ActividadPublica,
    DesafioFindIt,
    VerificacionFindIt,
    EstadoAnalisis,
)


def _cargar_prompt_exploracion() -> str:
    """Lee las instrucciones de exploración del archivo versionado."""
    ruta_prompt = Path(__file__).parent / "prompts" / "exploracion.txt"
    if ruta_prompt.exists():
        try:
            return ruta_prompt.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "You are HomeLens English. Analyze the image and extract prominent everyday objects with quiz questions."


def obtener_actividades_publicas(actividades: list[Actividad]) -> list[ActividadPublica]:
    """Proyecta las actividades del dominio a su versión pública sin revelar la respuesta."""
    return [
        ActividadPublica(
            actividad_id=act.actividad_id,
            pregunta=act.pregunta,
            opciones=act.opciones,
        )
        for act in actividades
    ]


def analizar_exploracion(
    usuario: ContextoUsuario,
    imagen: ImagenPreparada,
    operacion_id: UUID,
    adaptador: Optional[AdaptadorGemini] = None,
) -> Resultado[Exploracion]:
    """Analiza una imagen mediante Gemini y genera objetos educativos y preguntas de práctica.

    Aplica validación estricta sobre coordenadas, límites de objetos, integridad de
    preguntas y coherencia de referencias antes de construir la Exploración.

    Args:
        usuario: Contexto de identidad del usuario activo.
        imagen: Imagen preparada y validada en memoria.
        operacion_id: Identificador único de trazabilidad de la operación.
        adaptador: Adaptador de Gemini opcional (permite inyección de mocks para pruebas).

    Returns:
        Resultado[Exploracion]: Exploración validada con objetos y actividades, o error controlado.
    """
    if not imagen or not imagen.contenido:
        return Resultado.fallo(
            codigo=CODIGO_IMAGEN_INVALIDA,
            mensaje_usuario="No se proporcionó una imagen válida para analizar.",
            reintentable=False,
            operacion_id=operacion_id,
        )

    # 1. Obtener adaptador configurado
    cliente_gemini = adaptador
    if cliente_gemini is None:
        cfg_res = cargar_configuracion()
        if not cfg_res.ok or not cfg_res.valor:
            return Resultado.fallo(
                codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                mensaje_usuario="No se pudo cargar la configuración para conectar con Gemini.",
                reintentable=False,
                operacion_id=operacion_id,
            )
        config = cfg_res.valor
        cliente_gemini = AdaptadorGemini(
            api_key=config.gemini_api_key,
            modelo=config.gemini_model,
        )

    # 2. Cargar prompt e invocar modelo
    prompt = _cargar_prompt_exploracion()
    res_ia = cliente_gemini.analizar_imagen_exploracion(
        imagen_bytes=imagen.contenido,
        mime_type=imagen.mime_type,
        instrucciones=prompt,
        operacion_id=operacion_id,
    )

    if not res_ia.ok or res_ia.valor is None:
        return Resultado.fallo(error=res_ia.error)

    respuesta_ia: RespuestaExploracionIA = res_ia.valor

    # 3. Validar y procesar según el estado retornado
    estado_raw = (respuesta_ia.estado or "").strip().upper()
    try:
        estado_analisis = EstadoAnalisis(estado_raw)
    except ValueError:
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario=f"El estado de análisis retornado ('{estado_raw}') no es reconocido.",
            reintentable=False,
            operacion_id=operacion_id,
        )

    exploracion_id = uuid4()
    ahora = datetime.now(timezone.utc)

    # Si la imagen no tiene objetos claros o requiere repetir captura, devolver exploración vacía válida
    if estado_analisis in (EstadoAnalisis.SIN_OBJETOS_CLAROS, EstadoAnalisis.REPETIR_CAPTURA):
        return Resultado.exito(
            Exploracion(
                exploracion_id=exploracion_id,
                user_id=usuario.user_id,
                creada_en=ahora,
                estado=estado_analisis,
                objetos=[],
                actividades=[],
                schema_version=1,
            )
        )

    # Si es UTILIZABLE, validar cantidad de objetos (1 a 5)
    if not respuesta_ia.objetos:
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario="El análisis se marcó como utilizable pero no devolvió ningún objeto detectado.",
            reintentable=False,
            operacion_id=operacion_id,
        )

    if len(respuesta_ia.objetos) > 5:
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario=f"El análisis devolvió {len(respuesta_ia.objetos)} objetos, superando el límite máximo de 5.",
            reintentable=False,
            operacion_id=operacion_id,
        )

    # 4. Validar y construir objetos educativos
    objetos_dominio: list[ObjetoEducativo] = []
    mapa_ids_locales: Dict[str, UUID] = {}

    for idx, obj_ia in enumerate(respuesta_ia.objetos, start=1):
        # Validaciones de cadenas no vacías
        nombre_en = (obj_ia.nombre_en or "").strip()
        nombre_es = (obj_ia.nombre_es or "").strip()
        frase_en = (obj_ia.frase_en or "").strip()
        frase_es = (obj_ia.frase_es or "").strip()
        id_local = (obj_ia.id_local or f"obj_{idx}").strip()

        if not nombre_en or not nombre_es:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"Objeto #{idx} incompleto: falta nombre en inglés o español.",
                reintentable=False,
                operacion_id=operacion_id,
            )

        if not frase_en or not frase_es:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"Objeto '{nombre_en}' incompleto: falta frase de ejemplo o su traducción.",
                reintentable=False,
                operacion_id=operacion_id,
            )

        # Validar recuadro y coordenadas
        rec = obj_ia.recuadro
        if rec is None:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"Objeto '{nombre_en}' no incluye recuadro de delimitación.",
                reintentable=False,
                operacion_id=operacion_id,
            )

        for coord, name in [(rec.ymin, "ymin"), (rec.xmin, "xmin"), (rec.ymax, "ymax"), (rec.xmax, "xmax")]:
            if not (0 <= coord <= 1000):
                return Resultado.fallo(
                    codigo=CODIGO_RESPUESTA_INVALIDA,
                    mensaje_usuario=f"Coordenada {name}={coord} en '{nombre_en}' fuera del rango permitido [0, 1000].",
                    reintentable=False,
                    operacion_id=operacion_id,
                )

        if rec.ymin >= rec.ymax:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"Coordenadas verticales inválidas en '{nombre_en}': ymin ({rec.ymin}) >= ymax ({rec.ymax}).",
                reintentable=False,
                operacion_id=operacion_id,
            )

        if rec.xmin >= rec.xmax:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"Coordenadas horizontales inválidas en '{nombre_en}': xmin ({rec.xmin}) >= xmax ({rec.xmax}).",
                reintentable=False,
                operacion_id=operacion_id,
            )

        obj_uuid = uuid4()
        mapa_ids_locales[id_local] = obj_uuid

        try:
            recuadro_norm = RecuadroNormalizado(
                ymin=rec.ymin,
                xmin=rec.xmin,
                ymax=rec.ymax,
                xmax=rec.xmax,
            )
        except ValueError as ve:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"Recuadro inválido en '{nombre_en}': {ve}",
                reintentable=False,
                operacion_id=operacion_id,
            )

        objetos_dominio.append(
            ObjetoEducativo(
                objeto_id=obj_uuid,
                exploracion_id=exploracion_id,
                nombre_en=nombre_en,
                nombre_es=nombre_es,
                recuadro=recuadro_norm,
                frase_en=frase_en,
                frase_es=frase_es,
            )
        )

    # 5. Validar y construir actividades pedagógicas
    actividades_dominio: list[Actividad] = []

    for act_idx, act_ia in enumerate(respuesta_ia.actividades, start=1):
        pregunta = (act_ia.pregunta or "").strip()
        explicacion = (act_ia.explicacion or "").strip()
        opcion_correcta_id = (act_ia.opcion_correcta_id or "").strip()

        if not pregunta:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"Actividad #{act_idx} no incluye el texto de la pregunta.",
                reintentable=False,
                operacion_id=operacion_id,
            )

        if len(act_ia.opciones) != 3:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"Actividad #{act_idx} debe tener exactamente 3 opciones, pero tiene {len(act_ia.opciones)}.",
                reintentable=False,
                operacion_id=operacion_id,
            )

        # Validar unicidad de opciones
        opciones_dominio: list[Opcion] = []
        ids_opciones_vistos = set()
        textos_opciones_vistos = set()

        for op_ia in act_ia.opciones:
            op_id = (op_ia.opcion_id or "").strip()
            op_txt = (op_ia.texto or "").strip()

            if not op_id or not op_txt:
                return Resultado.fallo(
                    codigo=CODIGO_RESPUESTA_INVALIDA,
                    mensaje_usuario=f"Opción inválida en actividad #{act_idx}: campos vacíos.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )

            if op_id in ids_opciones_vistos:
                return Resultado.fallo(
                    codigo=CODIGO_RESPUESTA_INVALIDA,
                    mensaje_usuario=f"Identificador de opción duplicado '{op_id}' en actividad #{act_idx}.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )

            if op_txt.lower() in textos_opciones_vistos:
                return Resultado.fallo(
                    codigo=CODIGO_RESPUESTA_INVALIDA,
                    mensaje_usuario=f"Texto de opción repetido '{op_txt}' en actividad #{act_idx}.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )

            ids_opciones_vistos.add(op_id)
            textos_opciones_vistos.add(op_txt.lower())
            opciones_dominio.append(Opcion(opcion_id=op_id, texto=op_txt))

        if opcion_correcta_id not in ids_opciones_vistos:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario=f"La opción correcta '{opcion_correcta_id}' no pertenece a las opciones de la actividad #{act_idx}.",
                reintentable=False,
                operacion_id=operacion_id,
            )

        # Resolver referencias a objetos
        objeto_uuids: list[UUID] = []
        for ref in act_ia.objetos_relacionados:
            ref_clean = ref.strip()
            if ref_clean in mapa_ids_locales:
                objeto_uuids.append(mapa_ids_locales[ref_clean])
            else:
                return Resultado.fallo(
                    codigo=CODIGO_RESPUESTA_INVALIDA,
                    mensaje_usuario=f"La actividad #{act_idx} referencia un objeto no reconocido ('{ref_clean}').",
                    reintentable=False,
                    operacion_id=operacion_id,
                )

        # Si no especificó referencias válidas explícitas, asociar al primer objeto por defecto
        if not objeto_uuids and objetos_dominio:
            objeto_uuids = [objetos_dominio[0].objeto_id]

        actividades_dominio.append(
            Actividad(
                actividad_id=uuid4(),
                exploracion_id=exploracion_id,
                objeto_ids=objeto_uuids,
                pregunta=pregunta,
                opciones=opciones_dominio,
                opcion_correcta_id=opcion_correcta_id,
                explicacion=explicacion,
            )
        )

    # 6. Construir y retornar entidad de exploración
    try:
        exploracion = Exploracion(
            exploracion_id=exploracion_id,
            user_id=usuario.user_id,
            creada_en=ahora,
            estado=estado_analisis,
            objetos=objetos_dominio,
            actividades=actividades_dominio,
            schema_version=1,
        )
        return Resultado.exito(exploracion)
    except ValueError as ve:
        return Resultado.fallo(
            codigo=CODIGO_RESPUESTA_INVALIDA,
            mensaje_usuario=f"Error de dominio al consolidar la exploración: {ve}",
            reintentable=False,
            operacion_id=operacion_id,
        )


def verificar_find_it(
    usuario: ContextoUsuario,
    imagen: ImagenPreparada,
    desafio: DesafioFindIt,
    operacion_id: UUID,
) -> Resultado[VerificacionFindIt]:
    """Verifica si la imagen contiene el objeto del desafío Find It (Parte 11)."""
    return Resultado.fallo(
        codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
        mensaje_usuario="La verificación de Find It se integrará en la Parte 11.",
        operacion_id=operacion_id,
    )
