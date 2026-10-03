"""Contratos de persistencia (M7) para HomeLens English."""

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from homelens.errores import Resultado
from homelens.modelos import (
    ContextoUsuario,
    Exploracion,
    ObjetoEducativo,
    Actividad,
    DesafioFindIt,
    IntentoPractica,
    Confirmacion,
)


class RepositorioHomeLens(ABC):
    """Contrato abstracto para el repositorio de datos de HomeLens."""

    @abstractmethod
    def guardar_exploracion(
        self, usuario: ContextoUsuario, exploracion: Exploracion
    ) -> Resultado[UUID]:
        """Guarda atómicamente una exploración con sus objetos y actividades."""
        pass

    @abstractmethod
    def obtener_exploracion(
        self, usuario: ContextoUsuario, exploracion_id: UUID
    ) -> Resultado[Exploracion]:
        """Obtiene una exploración verificando que pertenezca al usuario."""
        pass

    @abstractmethod
    def listar_vocabulario(
        self, usuario: ContextoUsuario
    ) -> Resultado[List[ObjetoEducativo]]:
        """Lista el vocabulario previamente explorado por el usuario."""
        pass

    @abstractmethod
    def guardar_desafio(
        self, usuario: ContextoUsuario, desafio: DesafioFindIt
    ) -> Resultado[UUID]:
        """Guarda un desafío Find It generado para el usuario."""
        pass

    @abstractmethod
    def obtener_desafio(
        self, usuario: ContextoUsuario, desafio_id: UUID
    ) -> Resultado[DesafioFindIt]:
        """Obtiene un desafío verificando pertenencia."""
        pass

    @abstractmethod
    def guardar_intento(
        self, usuario: ContextoUsuario, intento: IntentoPractica
    ) -> Resultado[Confirmacion]:
        """Registra de forma idempotente un intento de práctica."""
        pass

    @abstractmethod
    def listar_intentos(
        self, usuario: ContextoUsuario, desde: Optional[datetime] = None
    ) -> Resultado[List[IntentoPractica]]:
        """Lista los intentos realizados por el usuario."""
        pass
