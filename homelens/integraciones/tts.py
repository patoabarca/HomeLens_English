"""Cliente de Google Cloud TTS; no se construye ni se llama al importar."""

from __future__ import annotations

from homelens.modelos import SolicitudAudio


class ErrorConfiguracionTTS(Exception):
    """Faltan SDK, credenciales o permisos del servicio."""


class ErrorTiempoTTS(Exception):
    """El proveedor excedió el tiempo permitido."""


class ErrorProveedorTTS(Exception):
    """El proveedor no pudo sintetizar el texto."""


class AdaptadorTTS:
    """Sintetiza texto plano a MP3, con cliente inyectable y sin reintentos."""

    def __init__(
        self, idioma: str = "en-US", voz: str = "en-US-Standard-C",
        *, cliente=None, timeout_seconds: float = 10.0,
    ):
        self.idioma = idioma
        self.voz = voz
        self._cliente = cliente
        self._timeout_seconds = timeout_seconds

    def sintetizar(self, solicitud: SolicitudAudio) -> bytes:
        """Una única solicitud de texto (nunca SSML ni instrucciones)."""
        try:
            from google.cloud import texttospeech
            from google.auth.exceptions import DefaultCredentialsError, RefreshError
            from google.api_core.exceptions import (
                DeadlineExceeded, PermissionDenied, Unauthenticated,
            )
        except ImportError:
            raise ErrorConfiguracionTTS("SDK de TTS no disponible.") from None

        try:
            if self._cliente is None:
                self._cliente = texttospeech.TextToSpeechClient()
            respuesta = self._cliente.synthesize_speech(
                input=texttospeech.SynthesisInput(text=solicitud.texto),
                voice=texttospeech.VoiceSelectionParams(
                    language_code=solicitud.idioma, name=solicitud.voz,
                ),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=solicitud.velocidad,
                ),
                timeout=self._timeout_seconds,
                retry=None,
            )
            return respuesta.audio_content
        except (DefaultCredentialsError, RefreshError, PermissionDenied, Unauthenticated):
            raise ErrorConfiguracionTTS("Credenciales o permisos de TTS no disponibles.") from None
        except (DeadlineExceeded, TimeoutError):
            raise ErrorTiempoTTS("Se agotó el tiempo de TTS.") from None
        except Exception:
            raise ErrorProveedorTTS("TTS temporalmente no disponible.") from None
