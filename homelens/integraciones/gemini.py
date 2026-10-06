"""Adaptador para el cliente de Google Gemini (M3).

Encapsula la configuración, llamada multimodal con salida estructurada,
manejo controlado de excepciones y telemetría de consumo.
"""

from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from typing import Optional, Any
from uuid import UUID, uuid4

try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    GENAI_DISPONIBLE = True
except ImportError:
    genai = None  # type: ignore
    google_exceptions = None  # type: ignore
    GENAI_DISPONIBLE = False

from homelens.errores import (
    Resultado,
    CODIGO_SERVICIO_NO_DISPONIBLE,
    CODIGO_LIMITE_ALCANZADO,
    CODIGO_TIEMPO_AGOTADO,
    CODIGO_RESPUESTA_INVALIDA,
    CODIGO_ACCESO_DENEGADO,
)
from homelens.esquemas_ia import RespuestaExploracionIA
from homelens.modelos import EventoTecnico
from homelens.telemetria import registrar_evento


class AdaptadorGemini:
    """Encapsula las llamadas y esquemas hacia la API de Google Gemini."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        modelo: str = "gemini-2.5-flash",
        timeout_segundos: float = 60.0,
        max_reintentos: int = 1,
    ) -> None:
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        # Normalizar si viene el modelo antiguo gemini-1.5-flash
        if modelo in ("gemini-1.5-flash", "models/gemini-1.5-flash"):
            self.modelo = "gemini-2.5-flash"
        else:
            self.modelo = modelo
        self.timeout_segundos = timeout_segundos
        self.max_reintentos = max(0, min(max_reintentos, 3))
        self._configurado = False

    @property
    def esta_configurado(self) -> bool:
        """Indica si el adaptador cuenta con credencial válida configurada."""
        return bool(self.api_key)

    def _asegurar_cliente(self) -> None:
        """Inicializa la configuración de genai si aún no se realizó."""
        if not GENAI_DISPONIBLE:
            raise RuntimeError("El paquete 'google-generativeai' no está instalado en el entorno.")
        if not self._configurado and self.api_key:
            genai.configure(api_key=self.api_key, transport="rest")
            self._configurado = True

    def analizar_imagen_exploracion(
        self,
        imagen_bytes: bytes,
        mime_type: str,
        instrucciones: str,
        operacion_id: Optional[UUID] = None,
    ) -> Resultado[RespuestaExploracionIA]:
        """Envía una imagen a Gemini con instrucciones y esquema estructurado.

        Args:
            imagen_bytes: Bytes limpios de la imagen preparada.
            mime_type: Tipo MIME ('image/jpeg' o 'image/png').
            instrucciones: Prompt educativo versionado.
            operacion_id: Identificador único de la operación.

        Returns:
            Resultado[RespuestaExploracionIA]: Respuesta estructurada o error controlado.
        """
        op_id = operacion_id or uuid4()

        if not self.esta_configurado:
            return Resultado.fallo(
                codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                mensaje_usuario="El servicio de análisis con Gemini no está configurado (falta GEMINI_API_KEY).",
                reintentable=False,
                operacion_id=op_id,
            )

        if not GENAI_DISPONIBLE:
            return Resultado.fallo(
                codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                mensaje_usuario="El componente de integración con Gemini no está disponible en este entorno.",
                reintentable=False,
                operacion_id=op_id,
            )

        try:
            self._asegurar_cliente()
        except Exception as e:
            return Resultado.fallo(
                codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                mensaje_usuario="Error al inicializar el cliente de Gemini.",
                reintentable=False,
                operacion_id=op_id,
            )

        parte_imagen = {
            "mime_type": mime_type,
            "data": imagen_bytes,
        }

        # Configuración de generación con salida estructurada en JSON
        generation_config = {
            "temperature": 0.2,
            "response_mime_type": "application/json",
            "response_schema": RespuestaExploracionIA,
        }

        modelo_ia = genai.GenerativeModel(
            model_name=self.modelo,
            generation_config=generation_config,
            system_instruction=instrucciones,
        )

        intentos = 0
        reintentos_realizados = 0
        inicio = time.perf_counter()
        ultimo_error: Optional[Exception] = None

        while intentos <= self.max_reintentos:
            intentos += 1
            try:
                # Invocación multimodal a la API
                request_options = {"timeout": self.timeout_segundos}
                respuesta = modelo_ia.generate_content(
                    [parte_imagen, "Analyze this image and identify educational objects."],
                    request_options=request_options,
                )

                duracion_ms = int((time.perf_counter() - inicio) * 1000)

                # Extraer metadatos de uso si están disponibles
                uso_reportado = None
                if hasattr(respuesta, "usage_metadata") and respuesta.usage_metadata:
                    try:
                        uso_reportado = {
                            "prompt_token_count": getattr(respuesta.usage_metadata, "prompt_token_count", None),
                            "candidates_token_count": getattr(respuesta.usage_metadata, "candidates_token_count", None),
                            "total_token_count": getattr(respuesta.usage_metadata, "total_token_count", None),
                        }
                    except Exception:
                        uso_reportado = None

                # Registrar telemetría exitosa
                registrar_evento(
                    EventoTecnico(
                        operacion_id=op_id,
                        tipo_operacion="analisis_exploracion_gemini",
                        fecha=datetime.now(timezone.utc),
                        duracion_ms=duracion_ms,
                        estado="EXITO",
                        numero_llamadas=intentos,
                        numero_reintentos=reintentos_realizados,
                        uso_reportado=uso_reportado,
                    )
                )

                # Validar contenido de respuesta
                texto_respuesta = respuesta.text if hasattr(respuesta, "text") and respuesta.text else None
                if not texto_respuesta:
                    # Comprobar si hubo bloqueo de seguridad
                    bloqueo_mensaje = "La respuesta de Gemini fue bloqueada o vino vacía."
                    if hasattr(respuesta, "prompt_feedback") and getattr(respuesta.prompt_feedback, "block_reason", None):
                        bloqueo_mensaje = f"Contenido bloqueado por filtros del modelo: {respuesta.prompt_feedback.block_reason}"

                    return Resultado.fallo(
                        codigo=CODIGO_RESPUESTA_INVALIDA,
                        mensaje_usuario=bloqueo_mensaje,
                        reintentable=False,
                        operacion_id=op_id,
                    )

                # Parsear a través de Pydantic
                try:
                    respuesta_ia = RespuestaExploracionIA.model_validate_json(texto_respuesta)
                    return Resultado.exito(respuesta_ia)
                except Exception:
                    return Resultado.fallo(
                        codigo=CODIGO_RESPUESTA_INVALIDA,
                        mensaje_usuario="La respuesta de Gemini no se ajusta al esquema estructurado requerido.",
                        reintentable=False,
                        operacion_id=op_id,
                    )

            except Exception as exc:
                ultimo_error = exc
                if google_exceptions:
                    # Errores permanentes: no reintentar
                    if isinstance(exc, (google_exceptions.PermissionDenied, google_exceptions.Unauthenticated)):
                        break
                    if isinstance(exc, google_exceptions.InvalidArgument):
                        break
                    if isinstance(exc, google_exceptions.ResourceExhausted):
                        break

                # Si es reintentable y quedan intentos, esperar brevemente
                if intentos <= self.max_reintentos:
                    reintentos_realizados += 1
                    time.sleep(0.5 * intentos)

        duracion_ms = int((time.perf_counter() - inicio) * 1000)

        # Registrar telemetría de fallo
        registrar_evento(
            EventoTecnico(
                operacion_id=op_id,
                tipo_operacion="analisis_exploracion_gemini",
                fecha=datetime.now(timezone.utc),
                duracion_ms=duracion_ms,
                estado="ERROR",
                numero_llamadas=intentos,
                numero_reintentos=reintentos_realizados,
            )
        )

        return self._mapear_excepcion(ultimo_error, op_id)

    def _mapear_excepcion(self, exc: Optional[Exception], operacion_id: UUID) -> Resultado[RespuestaExploracionIA]:
        """Traduce excepciones del proveedor a errores de dominio sanitizados."""
        if exc is None:
            return Resultado.fallo(
                codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                mensaje_usuario="Error desconocido al comunicarse con Gemini.",
                reintentable=False,
                operacion_id=operacion_id,
            )

        if google_exceptions:
            if isinstance(exc, google_exceptions.ResourceExhausted):
                return Resultado.fallo(
                    codigo=CODIGO_LIMITE_ALCANZADO,
                    mensaje_usuario="Se ha alcanzado la cuota o límite de peticiones a Gemini. Intente más tarde.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )
            if isinstance(exc, (google_exceptions.PermissionDenied, google_exceptions.Unauthenticated)):
                return Resultado.fallo(
                    codigo=CODIGO_ACCESO_DENEGADO,
                    mensaje_usuario="Credenciales de Gemini inválidas o sin permisos suficientes.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )
            if isinstance(exc, (google_exceptions.DeadlineExceeded, TimeoutError)):
                return Resultado.fallo(
                    codigo=CODIGO_TIEMPO_AGOTADO,
                    mensaje_usuario="Tiempo de espera agotado al consultar el modelo Gemini.",
                    reintentable=True,
                    operacion_id=operacion_id,
                )
            if isinstance(exc, google_exceptions.InvalidArgument):
                return Resultado.fallo(
                    codigo=CODIGO_RESPUESTA_INVALIDA,
                    mensaje_usuario="Solicitud inválida enviada al modelo Gemini.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )

        nombre_error = type(exc).__name__.lower()
        if "timeout" in nombre_error:
            return Resultado.fallo(
                codigo=CODIGO_TIEMPO_AGOTADO,
                mensaje_usuario="Tiempo de espera agotado al consultar el modelo Gemini.",
                reintentable=True,
                operacion_id=operacion_id,
            )

        return Resultado.fallo(
            codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
            mensaje_usuario="El servicio de análisis visual con Gemini no está disponible en este momento.",
            reintentable=True,
            operacion_id=operacion_id,
        )
