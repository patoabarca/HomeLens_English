"""Adaptador para el cliente de Google Cloud Text-to-Speech (TTS)."""

from __future__ import annotations
from typing import Optional


class AdaptadorTTS:
    """Encapsula la síntesis de voz con Google Cloud TTS."""

    def __init__(self, idioma: str = "en-US", voz: str = "en-US-Standard-C"):
        self.idioma = idioma
        self.voz = voz
