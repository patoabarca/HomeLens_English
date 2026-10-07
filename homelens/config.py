"""Módulo M0: Configuración y entorno del sistema.

Permite cargar y validar la configuración de la aplicación de forma segura
sin exponer secretos ni credenciales en registros ni mensajes de error.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

from homelens.errores import Resultado, CODIGO_CONFIGURACION_INVALIDA


@dataclass(frozen=True)
class Configuracion:
    """Parámetros de configuración de servicios y límites operativos."""
    app_env: str
    debug: bool
    log_level: str
    app_port: int
    gemini_api_key: Optional[str]
    gemini_model: str
    gemini_timeout_seconds: float
    gemini_max_retries: int
    supabase_url: Optional[str]
    supabase_anon_key: Optional[str]
    supabase_service_role_key: Optional[str]
    google_tts_language_code: str
    google_tts_voice_name: str
    max_image_size_bytes: int
    audio_cache_ttl_seconds: int
    rate_limit_exploraciones_por_minuto: int

    @property
    def tiene_gemini(self) -> bool:
        """Indica si la clave de Gemini está configurada."""
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    @property
    def tiene_supabase(self) -> bool:
        """Indica si la configuración básica de Supabase está presente."""
        return bool(self.supabase_url and self.supabase_anon_key)


def cargar_configuracion(ruta_env: Optional[str] = None) -> Resultado[Configuracion]:
    """Carga y valida las variables de entorno desde el archivo .env o el entorno del sistema.

    Returns:
        Resultado[Configuracion]: Resultado con el objeto de configuración o error sanitizado.
    """
    try:
        # Cargar variables de entorno si existe el archivo
        if ruta_env and os.path.exists(ruta_env):
            load_dotenv(dotenv_path=ruta_env, override=False)
        else:
            load_dotenv(override=False)

        app_env = os.getenv("APP_ENV", "development").strip().lower()
        debug = os.getenv("DEBUG", "true").strip().lower() in ("true", "1", "yes")
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()

        try:
            app_port = int(os.getenv("APP_PORT", "8501"))
        except ValueError:
            app_port = 8501

        gemini_api_key = os.getenv("GEMINI_API_KEY")
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

        try:
            gemini_timeout_seconds = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "60.0"))
        except ValueError:
            gemini_timeout_seconds = 60.0

        try:
            gemini_max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "1"))
        except ValueError:
            gemini_max_retries = 1

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        google_tts_language_code = os.getenv("GOOGLE_TTS_LANGUAGE_CODE", "en-US").strip()
        google_tts_voice_name = os.getenv("GOOGLE_TTS_VOICE_NAME", "en-US-Standard-C").strip()

        try:
            max_image_size_bytes = int(os.getenv("MAX_IMAGE_SIZE_BYTES", "10000000"))
        except ValueError:
            max_image_size_bytes = 10_000_000

        try:
            audio_cache_ttl_seconds = int(os.getenv("AUDIO_CACHE_TTL_SECONDS", "3600"))
        except ValueError:
            audio_cache_ttl_seconds = 3600

        try:
            rate_limit_exploraciones_por_minuto = int(os.getenv("RATE_LIMIT_EXPLORACIONES_POR_MINUTO", "10"))
        except ValueError:
            rate_limit_exploraciones_por_minuto = 10

        config = Configuracion(
            app_env=app_env,
            debug=debug,
            log_level=log_level,
            app_port=app_port,
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
            gemini_timeout_seconds=gemini_timeout_seconds,
            gemini_max_retries=gemini_max_retries,
            supabase_url=supabase_url,
            supabase_anon_key=supabase_anon_key,
            supabase_service_role_key=supabase_service_role_key,
            google_tts_language_code=google_tts_language_code,
            google_tts_voice_name=google_tts_voice_name,
            max_image_size_bytes=max_image_size_bytes,
            audio_cache_ttl_seconds=audio_cache_ttl_seconds,
            rate_limit_exploraciones_por_minuto=rate_limit_exploraciones_por_minuto,
        )

        return Resultado.exito(config)

    except Exception as e:
        return Resultado.fallo(
            codigo=CODIGO_CONFIGURACION_INVALIDA,
            mensaje_usuario="No se pudo cargar la configuración de la aplicación.",
            reintentable=False,
        )
