"""M5 con clientes simulados: esta suite nunca consume cuota de TTS."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from homelens import audio
from homelens.errores import Resultado
from homelens.integraciones.tts import (
    AdaptadorTTS, ErrorConfiguracionTTS, ErrorProveedorTTS, ErrorTiempoTTS,
)
from homelens.modelos import ContextoUsuario, SolicitudAudio, AudioDisponible


MP3 = Path(__file__).with_name("fixtures").joinpath("audio_simulado.mp3").read_bytes()
CREAR_REAL = audio._crear_adaptador


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    audio._CACHE_AUDIO_SESION.clear()
    audio._EN_CURSO.clear()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("GOOGLE_TTS_ENABLED", "false")
    monkeypatch.setattr(audio, "cargar_configuracion", lambda: Resultado.exito(
        SimpleNamespace(audio_cache_ttl_seconds=60),
    ))
    cliente = Mock()
    cliente.sintetizar.return_value = MP3
    fabrica = Mock(return_value=cliente)
    monkeypatch.setattr(audio, "_crear_adaptador", fabrica)
    yield SimpleNamespace(cliente=cliente, fabrica=fabrica)
    audio._CACHE_AUDIO_SESION.clear()
    audio._EN_CURSO.clear()


@pytest.fixture
def usuario():
    return ContextoUsuario(uuid4(), "sesion-comprobada")


def pedir(usuario, texto="Chair", **kwargs):
    return audio.obtener_audio(usuario, SolicitudAudio(texto, **kwargs), uuid4())


def test_modelos_cache_y_reproduccion_repetida(usuario, entorno):
    primero, segundo = pedir(usuario), pedir(usuario)
    assert primero.ok and segundo.ok
    assert isinstance(primero.valor, AudioDisponible)
    assert primero.valor.contenido == MP3
    assert primero.valor.mime_type == "audio/mpeg"
    assert primero.valor.generado_en.tzinfo is not None
    assert not primero.valor.reutilizado and segundo.valor.reutilizado
    entorno.cliente.sintetizar.assert_called_once_with(SolicitudAudio("Chair"))


@pytest.mark.parametrize("cambio", [
    dict(texto="This is a comfortable chair."), dict(voz="en-US-Standard-D"),
    dict(velocidad=0.8), dict(idioma="en-GB", voz="en-GB-Standard-A"),
])
def test_diferencia_texto_idioma_voz_velocidad(usuario, entorno, cambio):
    assert pedir(usuario).ok
    solicitud = replace(SolicitudAudio("Chair"), **cambio)
    assert audio.obtener_audio(usuario, solicitud, uuid4()).ok
    assert entorno.cliente.sintetizar.call_count == 2


def test_usuarios_y_sesiones_separados(usuario, entorno):
    for u in (usuario, replace(usuario, user_id=uuid4()), replace(usuario, sesion_id="otra")):
        assert pedir(u).ok
    assert entorno.cliente.sintetizar.call_count == 3
    assert len(audio._CACHE_AUDIO_SESION) == 3
    assert all("sesion-comprobada" not in k for k in audio._CACHE_AUDIO_SESION)


def test_vencimiento_no_se_extiende_al_reutilizar(usuario, entorno, monkeypatch):
    reloj = Mock(return_value=100)
    monkeypatch.setattr(audio, "monotonic", reloj)
    assert pedir(usuario).ok
    reloj.return_value = 159
    assert pedir(usuario).valor.reutilizado
    reloj.return_value = 160
    assert audio._consultar_audio_cache(usuario, SolicitudAudio("Chair")) is None
    assert pedir(usuario).ok
    assert entorno.cliente.sintetizar.call_count == 2


def test_limpieza_solo_sesion_indicada(usuario, entorno):
    otro = replace(usuario, sesion_id="otra")
    pedir(usuario)
    pedir(otro)
    audio.limpiar_cache_audio(usuario.sesion_id)
    assert pedir(otro).valor.reutilizado
    assert not pedir(usuario).valor.reutilizado
    assert entorno.cliente.sintetizar.call_count == 3


@pytest.mark.parametrize("texto", ["", "  ", "a" * 501, "123", "Chair\x00", "Chair\n", "\ud800", "<speak>Chair</speak>", None, 42])
def test_textos_invalidos_sin_llamadas(usuario, entorno, texto):
    resultado = pedir(usuario, texto)
    assert not resultado.ok and resultado.error.codigo == "RESPUESTA_INVALIDA"
    entorno.fabrica.assert_not_called()


@pytest.mark.parametrize("cambio", [
    dict(velocidad=float("nan")), dict(velocidad=True), dict(velocidad=3),
    dict(velocidad="1"), dict(velocidad=10**400),
    dict(idioma="es-AR"), dict(voz="en-US-Neural2-C"),
])
def test_parametros_invalidos(usuario, entorno, cambio):
    solicitud = replace(SolicitudAudio("Chair"), **cambio)
    assert not audio.obtener_audio(usuario, solicitud, uuid4()).ok
    entorno.fabrica.assert_not_called()


@pytest.mark.parametrize("sesion", [None, "", " ", "\ud800"])
def test_sesion_requerida(usuario, entorno, sesion):
    res = pedir(replace(usuario, sesion_id=sesion))
    assert res.error.codigo == "SESION_REQUERIDA"
    entorno.fabrica.assert_not_called()


@pytest.mark.parametrize("error,codigo", [
    (ErrorConfiguracionTTS("SECRETO"), "CONFIGURACION_INVALIDA"),
    (ErrorTiempoTTS("SECRETO"), "TIEMPO_AGOTADO"),
    (ErrorProveedorTTS("SECRETO"), "SERVICIO_NO_DISPONIBLE"),
    (RuntimeError("SECRETO"), "SERVICIO_NO_DISPONIBLE"),
])
def test_error_sanitizado_y_no_cacheado(usuario, entorno, error, codigo):
    entorno.cliente.sintetizar.side_effect = error
    res = pedir(usuario)
    assert not res.ok and res.error.codigo == codigo
    assert "SECRETO" not in res.error.mensaje_usuario
    assert audio._consultar_audio_cache(usuario, SolicitudAudio("Chair")) is None
    entorno.cliente.sintetizar.side_effect = None
    assert pedir(usuario).ok


@pytest.mark.parametrize("contenido", [b"", "url", b"a" * (audio.MAX_BYTES_AUDIO + 1)], ids=["vacio", "tipo", "excesivo"])
def test_respuesta_invalida(usuario, entorno, contenido):
    entorno.cliente.sintetizar.return_value = contenido
    assert pedir(usuario).error.codigo == "RESPUESTA_INVALIDA"


def test_ttl_invalido_no_llama(usuario, entorno, monkeypatch):
    monkeypatch.setattr(audio, "cargar_configuracion", lambda: Resultado.exito(
        SimpleNamespace(audio_cache_ttl_seconds=0),
    ))
    assert pedir(usuario).error.codigo == "CONFIGURACION_INVALIDA"
    entorno.fabrica.assert_not_called()


@pytest.mark.parametrize("cerrar", [False, True])
def test_concurrencia_deduplica_y_cierre_invalida(usuario, entorno, cerrar):
    iniciado, liberar, esperando = Event(), Event(), Event()

    def sintetizar(_):
        iniciado.set()
        assert liberar.wait(5)
        return MP3

    entorno.cliente.sintetizar.side_effect = sintetizar
    with ThreadPoolExecutor(max_workers=2) as pool:
        primero = pool.submit(pedir, usuario)
        assert iniciado.wait(3)
        futuro_compartido = next(iter(audio._EN_CURSO.values()))
        resultado_original = futuro_compartido.result

        def esperar(*args, **kwargs):
            esperando.set()
            return resultado_original(*args, **kwargs)

        futuro_compartido.result = esperar
        segundo = pool.submit(pedir, usuario)
        assert esperando.wait(3)
        if cerrar:
            audio.limpiar_cache_audio(usuario.sesion_id)
        liberar.set()
        resultados = [primero.result(5), segundo.result(5)]
    entorno.cliente.sintetizar.assert_called_once()
    assert not audio._EN_CURSO
    if cerrar:
        assert all(r.error.codigo == "SESION_REQUERIDA" for r in resultados)
        assert not audio._CACHE_AUDIO_SESION
    else:
        assert all(r.ok for r in resultados)
        assert resultados[1].valor.reutilizado


def test_limites_memoria_y_lru(usuario, entorno, monkeypatch):
    monkeypatch.setattr(audio, "MAX_ENTRADAS_SESION", 2)
    for texto in ("Chair", "Table", "Lamp"):
        pedir(usuario, texto)
    assert audio._consultar_audio_cache(usuario, SolicitudAudio("Chair")) is None
    assert pedir(usuario, "Table").valor.reutilizado
    monkeypatch.setattr(audio, "MAX_BYTES_SESION", len(MP3))
    pedir(usuario, "Book")
    assert sum(len(c.entradas) for c in audio._CACHE_AUDIO_SESION.values()) == 1
    monkeypatch.setattr(audio, "MAX_SESIONES", 2)
    for i in range(5):
        pedir(replace(usuario, sesion_id=str(i)))
    assert len(audio._CACHE_AUDIO_SESION) == 2
    monkeypatch.setattr(audio, "MAX_BYTES_TOTAL", len(MP3))
    pedir(replace(usuario, sesion_id="ultima"))
    assert sum(audio._bytes(c) for c in audio._CACHE_AUDIO_SESION.values()) <= len(MP3)


@pytest.mark.parametrize("demo,app_env,enabled", [
    (False, "development", "false"), (True, "development", "true"),
    (False, "test", "true"), (False, "testing", "true"),
])
def test_bloqueo_real_por_defecto_demo_y_test(usuario, entorno, monkeypatch, demo, app_env, enabled):
    monkeypatch.setattr(audio, "_crear_adaptador", CREAR_REAL)
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("GOOGLE_TTS_ENABLED", enabled)
    constructor = Mock(side_effect=AssertionError("No construir cliente real"))
    monkeypatch.setattr(audio, "AdaptadorTTS", constructor)
    assert pedir(replace(usuario, es_demo=demo)).error.codigo == "CONFIGURACION_INVALIDA"
    constructor.assert_not_called()


def test_adaptador_mp3_texto_plano_timeout_sin_retry():
    cliente = Mock()
    cliente.synthesize_speech.return_value = SimpleNamespace(audio_content=MP3)
    adaptador = AdaptadorTTS(cliente=cliente)
    assert adaptador.sintetizar(SolicitudAudio("Chair")) == MP3
    kwargs = cliente.synthesize_speech.call_args.kwargs
    assert kwargs["input"].text == "Chair" and not kwargs["input"].ssml
    assert kwargs["voice"].name == "en-US-Standard-C"
    assert kwargs["audio_config"].speaking_rate == 1
    assert kwargs["timeout"] == 10 and kwargs["retry"] is None


def test_credenciales_faltantes_sin_consultar_red(monkeypatch):
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import texttospeech
    constructor = Mock(side_effect=DefaultCredentialsError("SECRETO"))
    monkeypatch.setattr(texttospeech, "TextToSpeechClient", constructor)
    with pytest.raises(ErrorConfiguracionTTS, match="Credenciales") as error:
        AdaptadorTTS().sintetizar(SolicitudAudio("Chair"))
    assert "SECRETO" not in str(error.value)


def test_timeout_sdk_y_error_proveedor():
    from google.api_core.exceptions import DeadlineExceeded
    cliente = Mock()
    for error, esperado in [(DeadlineExceeded("SECRETO"), ErrorTiempoTTS),
                            (RuntimeError("SECRETO"), ErrorProveedorTTS)]:
        cliente.synthesize_speech.side_effect = error
        with pytest.raises(esperado) as capturado:
            AdaptadorTTS(cliente=cliente).sintetizar(SolicitudAudio("Chair"))
        assert "SECRETO" not in str(capturado.value)
