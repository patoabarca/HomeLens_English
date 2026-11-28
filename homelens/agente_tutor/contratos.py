"""Contratos de dominio y esquemas Pydantic para el Agente Tutor de HomeLens English."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel


# =====================================================================
# 1. Esquemas Pydantic para salidas estructuradas de Gemini
# =====================================================================

class EsquemaActividadTutorIA(BaseModel):
    """Esquema JSON estructurado que Gemini devuelve para preparar-actividad."""
    consigna: str
    objeto_ids_elegidos: List[str]
    objeto_objetivo_id: str
    criterio_correccion: str
    respuestas_aceptadas: List[str]
    es_refuerzo: bool


class EsquemaEvaluacionTutorIA(BaseModel):
    """Esquema JSON estructurado que Gemini devuelve para evaluar-respuesta."""
    valoracion: Literal["CORRECTA", "PARCIAL", "INCORRECTA"]
    devolucion: str
    dificultad_detectada: Optional[str] = None
    objeto_confundido_id: Optional[str] = None


class EsquemaPistaTutorIA(BaseModel):
    """Esquema JSON estructurado que Gemini devuelve para dar-pista."""
    texto_pista: str
    objeto_resaltado_id: Optional[str] = None


class EsquemaDecisionOrquestadorIA(BaseModel):
    """Esquema JSON estructurado que Gemini devuelve para decidir la acción pedagógica."""
    accion_siguiente: Literal[
        "AVANZAR",
        "PERMITIR_OTRO_INTENTO",
        "OFRECER_PISTA",
        "PREPARAR_REFUERZO",
        "CERRAR",
    ]
    motivo: str
    mensaje_transicion: str


# =====================================================================
# 2. Entidades del dominio y estado de sesión del Agente Tutor
# =====================================================================

@dataclass(frozen=True)
class ActividadTutor:
    """Actividad breve preparada sobre entre 1 y 3 objetos de la foto activa."""
    actividad_tutor_id: str
    consigna: str
    objeto_ids: list[str]
    objeto_objetivo_id: str
    criterio_correccion: str
    respuestas_aceptadas: list[str] = field(default_factory=list)
    es_refuerzo: bool = False
    foco_dificultad: Optional[str] = None

    def vista_alumno(self) -> Dict[str, Any]:
        """Proyección pública para la interfaz: excluye el criterio interno y las respuestas aceptadas."""
        return {
            "actividad_tutor_id": self.actividad_tutor_id,
            "consigna": self.consigna,
            "objeto_ids": list(self.objeto_ids),
            "es_refuerzo": self.es_refuerzo,
        }


@dataclass(frozen=True)
class EvaluacionTutor:
    """Resultado estructurado de evaluar la respuesta del alumno."""
    valoracion: Literal["CORRECTA", "PARCIAL", "INCORRECTA"]
    devolucion: str
    dificultad_detectada: Optional[str] = None
    objeto_confundido_id: Optional[str] = None


@dataclass(frozen=True)
class PistaTutor:
    """Ayuda breve generada por la skill dar-pista."""
    numero_pista: int
    texto_pista: str
    objeto_resaltado_id: Optional[str] = None
    origen: Literal["SOLICITUD_ALUMNO", "DECISION_TUTOR"] = "SOLICITUD_ALUMNO"


@dataclass(frozen=True)
class RegistroEventoTutor:
    """Evento observable de trazabilidad para auditar el recorrido en la defensa."""
    paso: int
    timestamp_utc: str
    evento_usuario: str
    skill_ejecutada: str
    decision_politica: Literal["AUTORIZADA", "BLOQUEADA"]
    accion_pedagogica: str
    resumen_observable: str
    conteo_respuestas: int
    conteo_pistas: int


@dataclass
class EstadoPracticaTutor:
    """Estado mutable por sesión de la práctica guiada con el Agente Tutor."""
    exploracion_id: str
    estado: Literal["INACTIVA", "ESPERANDO_RESPUESTA", "EVALUADA", "FINALIZADA"] = "INACTIVA"
    actividad_actual: Optional[ActividadTutor] = None
    turnos_consumidos: int = 0
    intentos_actividad_actual: int = 0
    pistas_actividad_actual: list[PistaTutor] = field(default_factory=list)
    pistas_totales: int = 0
    refuerzos_realizados: int = 0
    objetos_practicados_ids: list[str] = field(default_factory=list)
    ultima_evaluacion: Optional[EvaluacionTutor] = None
    ultima_accion_pedagogica: Optional[str] = None
    mensaje_transicion: Optional[str] = None
    objeto_resaltado_id: Optional[str] = None
    historial_respuestas: list[Dict[str, Any]] = field(default_factory=list)
    traza_observable: list[RegistroEventoTutor] = field(default_factory=list)
    ultimo_evento_id_procesado: Optional[str] = None
    error_actual: Optional[str] = None
    mensaje_cierre: Optional[str] = None

    def registrar_traza(
        self,
        evento_usuario: str,
        skill_ejecutada: str,
        decision_politica: Literal["AUTORIZADA", "BLOQUEADA"],
        accion_pedagogica: str,
        resumen_observable: str,
    ) -> RegistroEventoTutor:
        evento = RegistroEventoTutor(
            paso=len(self.traza_observable) + 1,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            evento_usuario=evento_usuario,
            skill_ejecutada=skill_ejecutada,
            decision_politica=decision_politica,
            accion_pedagogica=accion_pedagogica,
            resumen_observable=resumen_observable,
            conteo_respuestas=self.turnos_consumidos,
            conteo_pistas=self.pistas_totales,
        )
        self.traza_observable.append(evento)
        return evento
