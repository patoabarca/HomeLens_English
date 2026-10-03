"""Definición de errores y contenedor de resultados (Resultado[T])."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional
from uuid import UUID, uuid4

# Códigos de error estándar del dominio
CODIGO_CONFIGURACION_INVALIDA = "CONFIGURACION_INVALIDA"
CODIGO_SESION_REQUERIDA = "SESION_REQUERIDA"
CODIGO_ACCESO_DENEGADO = "ACCESO_DENEGADO"
CODIGO_IMAGEN_INVALIDA = "IMAGEN_INVALIDA"
CODIGO_LIMITE_ALCANZADO = "LIMITE_ALCANZADO"
CODIGO_TIEMPO_AGOTADO = "TIEMPO_AGOTADO"
CODIGO_SERVICIO_NO_DISPONIBLE = "SERVICIO_NO_DISPONIBLE"
CODIGO_RESPUESTA_INVALIDA = "RESPUESTA_INVALIDA"
CODIGO_PERSISTENCIA_FALLIDA = "PERSISTENCIA_FALLIDA"


@dataclass(frozen=True)
class ErrorOperacion:
    """Representa un error controlado en una operación del sistema."""
    codigo: str
    mensaje_usuario: str
    reintentable: bool
    operacion_id: UUID

    @classmethod
    def crear(
        cls,
        codigo: str,
        mensaje_usuario: str,
        reintentable: bool = False,
        operacion_id: Optional[UUID] = None,
    ) -> ErrorOperacion:
        return cls(
            codigo=codigo,
            mensaje_usuario=mensaje_usuario,
            reintentable=reintentable,
            operacion_id=operacion_id or uuid4(),
        )


T = TypeVar("T")


@dataclass(frozen=True)
class Resultado(Generic[T]):
    """Contenedor de resultado para operaciones que pueden fallar de forma controlada."""
    ok: bool
    valor: Optional[T] = None
    error: Optional[ErrorOperacion] = None

    def __post_init__(self) -> None:
        if self.ok and self.error is not None:
            raise ValueError("Un Resultado exitoso no debe contener un error.")
        if not self.ok and self.error is None:
            raise ValueError("Un Resultado fallido debe contener un ErrorOperacion.")

    @classmethod
    def exito(cls, valor: T) -> Resultado[T]:
        """Crea un resultado exitoso con su valor."""
        return cls(ok=True, valor=valor, error=None)

    @classmethod
    def fallo(
        cls,
        error: ErrorOperacion | None = None,
        *,
        codigo: str | None = None,
        mensaje_usuario: str | None = None,
        reintentable: bool = False,
        operacion_id: Optional[UUID] = None,
    ) -> Resultado[T]:
        """Crea un resultado fallido a partir de un ErrorOperacion o de parámetros individuales."""
        if error is not None:
            return cls(ok=False, valor=None, error=error)
        if codigo is None or mensaje_usuario is None:
            raise ValueError("Debe especificarse un error o (codigo y mensaje_usuario).")
        err = ErrorOperacion.crear(
            codigo=codigo,
            mensaje_usuario=mensaje_usuario,
            reintentable=reintentable,
            operacion_id=operacion_id,
        )
        return cls(ok=False, valor=None, error=err)
