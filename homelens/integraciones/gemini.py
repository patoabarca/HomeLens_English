"""Adaptador para el cliente de Google Gemini."""

from __future__ import annotations
from typing import Optional


class AdaptadorGemini:
    """Encapsula las llamadas y esquemas hacia la API de Google Gemini."""

    def __init__(self, api_key: Optional[str] = None, modelo: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.modelo = modelo
