"""Modelos de dominio compartidos de HomeLens English.

Estas estructuras definen el núcleo del dominio educativo sin dependencias
de Streamlit, bases de datos externas ni clientes específicos de IA.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


# =====================================================================
# 1. Contexto e Identidad
# =====================================================================

@dataclass(frozen=True)
class ContextoUsuario:
    """Representa la identidad comprobada del usuario en el servidor."""
    user_id: UUID
    sesion_id: str


# =====================================================================
# 2. Imágenes y Geometría
# =====================================================================

@dataclass(frozen=True)
class ImagenPreparada:
    """Imagen validada y procesada temporalmente en memoria."""
    contenido: bytes
    mime_type: str
    ancho: int
    alto: int


@dataclass(frozen=True)
class RecuadroNormalizado:
    """Coordenadas normalizadas [0, 1000] en orden [ymin, xmin, ymax, xmax]."""
    ymin: int
    xmin: int
    ymax: int
    xmax: int

    def __post_init__(self) -> None:
        for val, name in [(self.ymin, "ymin"), (self.xmin, "xmin"), (self.ymax, "ymax"), (self.xmax, "xmax")]:
            if not (0 <= val <= 1000):
                raise ValueError(f"El valor de {name} ({val}) debe estar entre 0 y 1000.")
        if self.ymin >= self.ymax:
            raise ValueError(f"ymin ({self.ymin}) debe ser menor que ymax ({self.ymax}).")
        if self.xmin >= self.xmax:
            raise ValueError(f"xmin ({self.xmin}) debe ser menor que xmax ({self.xmax}).")


@dataclass(frozen=True)
class RecuadroPantalla:
    """Coordenadas calculadas para el tamaño efectivo de la imagen en pantalla."""
    izquierda: float
    arriba: float
    ancho: float
    alto: float


# =====================================================================
# 3. Exploración y Objetos Educativos
# =====================================================================

class EstadoAnalisis(str, Enum):
    UTILIZABLE = "UTILIZABLE"
    SIN_OBJETOS_CLAROS = "SIN_OBJETOS_CLAROS"
    REPETIR_CAPTURA = "REPETIR_CAPTURA"


@dataclass(frozen=True)
class ObjetoEducativo:
    """Vocabulario educativo detectado en una imagen."""
    objeto_id: UUID
    exploracion_id: UUID
    nombre_en: str
    nombre_es: str
    recuadro: RecuadroNormalizado
    frase_en: str
    frase_es: str


@dataclass(frozen=True)
class Opcion:
    """Opción de respuesta para una actividad de evaluación."""
    opcion_id: str
    texto: str


@dataclass(frozen=True)
class Actividad:
    """Actividad de práctica completa con solución e información pedagógica."""
    actividad_id: UUID
    exploracion_id: UUID
    objeto_ids: list[UUID]
    pregunta: str
    opciones: list[Opcion]
    opcion_correcta_id: str
    explicacion: str

    def __post_init__(self) -> None:
        if len(self.opciones) != 3:
            raise ValueError("Una actividad debe tener exactamente 3 opciones.")
        ids_opciones = [o.opcion_id for o in self.opciones]
        if self.opcion_correcta_id not in ids_opciones:
            raise ValueError("La opción correcta debe pertenecer a la lista de opciones.")


@dataclass(frozen=True)
class ActividadPublica:
    """Versión segura de la actividad enviada a la vista antes de confirmar."""
    actividad_id: UUID
    pregunta: str
    opciones: list[Opcion]


@dataclass(frozen=True)
class TarjetaObjeto:
    """Proyección visual de un objeto para mostrar en la interfaz."""
    objeto_id: UUID
    nombre_en: str
    nombre_es: str
    frase_en: str
    frase_es: str
    recuadro_pantalla: Optional[RecuadroPantalla] = None


@dataclass(frozen=True)
class Exploracion:
    """Exploración visual y educativa completa realizada por un usuario."""
    exploracion_id: UUID
    user_id: UUID
    creada_en: datetime
    estado: EstadoAnalisis
    objetos: list[ObjetoEducativo] = field(default_factory=list)
    actividades: list[Actividad] = field(default_factory=list)
    schema_version: int = 1

    def __post_init__(self) -> None:
        if len(self.objetos) > 5:
            raise ValueError("Una exploración puede tener como máximo 5 objetos educativos.")


# =====================================================================
# 4. Desafíos Find It e Intentos de Práctica
# =====================================================================

class EstadoFindIt(str, Enum):
    ENCONTRADO = "ENCONTRADO"
    NO_ENCONTRADO = "NO_ENCONTRADO"
    INDETERMINABLE = "INDETERMINABLE"


@dataclass(frozen=True)
class VerificacionFindIt:
    """Resultado técnico del análisis de un desafío Find It."""
    estado: EstadoFindIt
    mensaje: str


@dataclass(frozen=True)
class DesafioFindIt:
    """Desafío de búsqueda generado a partir de vocabulario previo."""
    desafio_id: UUID
    user_id: UUID
    objeto_origen_id: UUID
    nombre_en: str
    nombre_es: str
    creado_en: datetime


class TipoIntento(str, Enum):
    CUESTIONARIO = "CUESTIONARIO"
    FIND_IT = "FIND_IT"


class ResultadoIntento(str, Enum):
    CORRECTO = "CORRECTO"
    INCORRECTO = "INCORRECTO"
    INDETERMINABLE = "INDETERMINABLE"


@dataclass(frozen=True)
class IntentoPractica:
    """Registro inmutable de un intento de práctica o desafío."""
    intento_id: UUID
    user_id: UUID
    tipo: TipoIntento
    fecha: datetime
    actividad_id: Optional[UUID] = None
    desafio_id: Optional[UUID] = None
    opcion_elegida_id: Optional[str] = None
    resultado: ResultadoIntento = ResultadoIntento.INCORRECTO
    objeto_ids: list[UUID] = field(default_factory=list)


@dataclass(frozen=True)
class ResultadoPractica:
    """Resultado devuelto a la vista tras procesar un intento."""
    intento_id: UUID
    resultado: ResultadoIntento
    explicacion: str
    registrado: bool


# =====================================================================
# 5. Audio (TTS) y Progreso
# =====================================================================

@dataclass(frozen=True)
class SolicitudAudio:
    """Petición controlada de síntesis de voz."""
    texto: str
    idioma: str = "en-US"
    voz: str = "en-US-Standard-C"
    velocidad: float = 1.0


@dataclass(frozen=True)
class AudioDisponible:
    """Audio generado o recuperado de la caché."""
    contenido: bytes
    mime_type: str
    generado_en: datetime
    reutilizado: bool


class EstadoPalabra(str, Enum):
    EXPLORADA = "EXPLORADA"
    PRACTICADA = "PRACTICADA"


@dataclass(frozen=True)
class PalabraResumen:
    """Resumen pedagógico de una palabra aprendida."""
    nombre_en: str
    nombre_es: str
    estado: EstadoPalabra
    ultima_practica: Optional[datetime] = None


@dataclass(frozen=True)
class ResumenProgreso:
    """Métricas y estado global de progreso de un estudiante."""
    palabras_exploradas: list[PalabraResumen]
    total_intentos: int
    resultados_por_tipo: dict[str, int]


# =====================================================================
# 6. Telemetría y Confirmaciones
# =====================================================================

@dataclass(frozen=True)
class EventoTecnico:
    """Registro técnico de métricas de rendimiento y consumo."""
    operacion_id: UUID
    tipo_operacion: str
    fecha: datetime
    duracion_ms: int
    estado: str
    numero_llamadas: int
    numero_reintentos: int
    uso_reportado: Optional[dict] = None
    costo_estimado: Optional[float] = None


@dataclass(frozen=True)
class Confirmacion:
    """Confirmación genérica de una operación ejecutada."""
    operacion_id: UUID
    mensaje: str
    ejecutada_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
