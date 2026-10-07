"""Adaptador para el cliente de Google Gemini (M3) mediante el SDK oficial google-genai.

Encapsula la configuración por instancia, llamada multimodal estructurada,
manejo controlado de excepciones y telemetría de consumo sin estado global.
"""

from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from typing import Optional, Any
from uuid import UUID, uuid4

try:
    from google import genai
    from google.genai import types, errors
    GENAI_DISPONIBLE = True
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore
    errors = None  # type: ignore
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
    """Encapsula las llamadas y esquemas hacia la API de Google Gemini usando google-genai."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        modelo: str = "gemini-2.5-flash",
        timeout_segundos: float = 60.0,
        max_reintentos: int = 1,
        cliente: Optional[Any] = None,
    ) -> None:
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.modelo = modelo
        self.timeout_segundos = max(1.0, float(timeout_segundos))
        self.max_reintentos = max(0, min(max_reintentos, 3))
        self._cliente_inyectado = cliente

    @property
    def esta_configurado(self) -> bool:
        """Indica si el adaptador cuenta con credencial válida configurada o cliente inyectado."""
        return bool(self._cliente_inyectado or self.api_key)

    def _obtener_cliente(self) -> Any:
        """Obtiene o crea una instancia independiente de genai.Client."""
        if self._cliente_inyectado is not None:
            return self._cliente_inyectado
        if not GENAI_DISPONIBLE:
            raise RuntimeError("El paquete 'google-genai' no está instalado en el entorno.")
        if not self.api_key:
            raise ValueError("Se requiere una clave API para instanciar el cliente de Gemini.")
        
        # Instancia local por sesión sin compartir estado global mutable
        return genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=int(self.timeout_segundos * 1000)),
        )

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
            operacion_id: Identificador único de trazabilidad.

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
                mensaje_usuario="El componente de integración con Gemini (google-genai) no está disponible.",
                reintentable=False,
                operacion_id=op_id,
            )

        try:
            cliente = self._obtener_cliente()
        except Exception as e:
            return Resultado.fallo(
                codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                mensaje_usuario="Error al inicializar el cliente de Gemini.",
                reintentable=False,
                operacion_id=op_id,
            )

        # Preparación de la parte multimodal de imagen y configuración de generación
        try:
            parte_imagen = types.Part.from_bytes(data=imagen_bytes, mime_type=mime_type)
            config_generacion = types.GenerateContentConfig(
                system_instruction=instrucciones,
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=RespuestaExploracionIA,
                http_options=types.HttpOptions(timeout=int(self.timeout_segundos * 1000)),
            )
        except Exception:
            return Resultado.fallo(
                codigo=CODIGO_RESPUESTA_INVALIDA,
                mensaje_usuario="Error al estructurar la solicitud para Gemini.",
                reintentable=False,
                operacion_id=op_id,
            )

        intentos = 0
        reintentos_realizados = 0
        inicio = time.perf_counter()
        ultimo_error: Optional[Exception] = None

        while intentos <= self.max_reintentos:
            intentos += 1
            try:
                # Invocación multimodal a la API mediante models.generate_content
                respuesta = cliente.models.generate_content(
                    model=self.modelo,
                    contents=[parte_imagen, "Analyze this image and identify educational objects according to instructions."],
                    config=config_generacion,
                )

                duracion_ms = int((time.perf_counter() - inicio) * 1000)

                # Extraer metadatos de consumo si están disponibles
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

                # Validar contenido de respuesta antes de registrar éxito
                texto_respuesta = getattr(respuesta, "text", None)
                if not texto_respuesta or not str(texto_respuesta).strip():
                    # Comprobar si hubo bloqueo o rechazo
                    bloqueo_mensaje = "La respuesta de Gemini fue bloqueada o vino vacía."
                    if hasattr(respuesta, "prompt_feedback") and getattr(respuesta.prompt_feedback, "block_reason", None):
                        bloqueo_mensaje = f"Contenido bloqueado por filtros de seguridad: {respuesta.prompt_feedback.block_reason}"

                    registrar_evento(
                        EventoTecnico(
                            operacion_id=op_id,
                            tipo_operacion="analisis_exploracion_gemini",
                            fecha=datetime.now(timezone.utc),
                            duracion_ms=duracion_ms,
                            estado="ERROR",
                            numero_llamadas=intentos,
                            numero_reintentos=reintentos_realizados,
                            uso_reportado=uso_reportado,
                        )
                    )

                    return Resultado.fallo(
                        codigo=CODIGO_RESPUESTA_INVALIDA,
                        mensaje_usuario=bloqueo_mensaje,
                        reintentable=False,
                        operacion_id=op_id,
                    )

                # Parsear y validar contra el esquema Pydantic
                try:
                    respuesta_ia = RespuestaExploracionIA.model_validate_json(texto_respuesta)
                except Exception:
                    registrar_evento(
                        EventoTecnico(
                            operacion_id=op_id,
                            tipo_operacion="analisis_exploracion_gemini",
                            fecha=datetime.now(timezone.utc),
                            duracion_ms=duracion_ms,
                            estado="ERROR",
                            numero_llamadas=intentos,
                            numero_reintentos=reintentos_realizados,
                            uso_reportado=uso_reportado,
                        )
                    )
                    return Resultado.fallo(
                        codigo=CODIGO_RESPUESTA_INVALIDA,
                        mensaje_usuario="La respuesta de Gemini no se ajusta al esquema estructurado requerido.",
                        reintentable=False,
                        operacion_id=op_id,
                    )

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

                return Resultado.exito(respuesta_ia)

            except Exception as exc:
                ultimo_error = exc

                # Clasificar si el error es permanente (NO reintentar)
                es_permanente = False
                if errors and isinstance(exc, errors.APIError):
                    # 4xx son errores de cliente/cuota/auth permanentes para este intento
                    if exc.code in (400, 401, 403, 404, 429):
                        es_permanente = True

                if es_permanente:
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

        if errors and isinstance(exc, errors.APIError):
            codigo_http = getattr(exc, "code", None)
            if codigo_http == 429:
                return Resultado.fallo(
                    codigo=CODIGO_LIMITE_ALCANZADO,
                    mensaje_usuario="Se ha alcanzado la cuota o límite de peticiones a Gemini. Intente más tarde.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )
            if codigo_http in (401, 403):
                return Resultado.fallo(
                    codigo=CODIGO_ACCESO_DENEGADO,
                    mensaje_usuario="Credenciales de Gemini inválidas o sin permisos suficientes.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )
            if codigo_http == 404:
                return Resultado.fallo(
                    codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                    mensaje_usuario=f"El modelo de Gemini '{self.modelo}' no fue encontrado o no está disponible.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )
            if codigo_http == 400:
                return Resultado.fallo(
                    codigo=CODIGO_RESPUESTA_INVALIDA,
                    mensaje_usuario="Solicitud inválida enviada al modelo Gemini.",
                    reintentable=False,
                    operacion_id=operacion_id,
                )
            if codigo_http in (500, 502, 503, 504):
                return Resultado.fallo(
                    codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                    mensaje_usuario="El servicio de análisis visual con Gemini no está disponible temporalmente.",
                    reintentable=True,
                    operacion_id=operacion_id,
                )

        nombre_error = type(exc).__name__.lower()
        msg_error = str(exc).lower()

        if "timeout" in nombre_error or "timeout" in msg_error or "deadline" in msg_error:
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
