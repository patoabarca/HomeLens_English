"""Pruebas de las tarjetas reales de M4 con MP3 y cliente simulados."""

from pathlib import Path
from unittest.mock import Mock
from dataclasses import replace

import pytest
from streamlit.testing.v1 import AppTest

from homelens import audio


PREVIEW = Path(__file__).resolve().parents[1] / "scripts/prueba_audio_simulado.py"


@pytest.fixture(autouse=True)
def sin_red(monkeypatch):
    import streamlit as st
    # AppTest de esta versión no serializa opciones con iconos en segmented_control.
    # Usar el selector equivalente nativo; la vista real se revisa en navegador.
    monkeypatch.setattr(st, "segmented_control", lambda *a, **kw: st.radio(*a, horizontal=True, **kw), raising=False)
    from google.cloud import texttospeech
    # Falla inmediatamente si algún camino intenta usar credenciales reales.
    monkeypatch.setattr(texttospeech, "TextToSpeechClient", Mock(side_effect=AssertionError("TTS real prohibido")))
    from homelens.integraciones.gemini import AdaptadorGemini
    gemini = Mock(side_effect=AssertionError("Gemini prohibido en audio"))
    monkeypatch.setattr(AdaptadorGemini, "__init__", gemini)
    audio._CACHE_AUDIO_SESION.clear()
    yield gemini
    gemini.assert_not_called()
    audio._CACHE_AUDIO_SESION.clear()


def iniciar():
    app = AppTest.from_file(str(PREVIEW), default_timeout=10).run()
    assert not app.exception
    return app


def boton(app, tipo="palabra", numero=0):
    return [b for b in app.button if b.key.startswith("audio_") and b.key.endswith(tipo)][numero]


def llamadas(app):
    return app.session_state.get("sim_llamadas", 0)


def test_tarjetas_no_sintetizan_y_click_generacion_cache(sin_red):
    app = iniciar()
    assert llamadas(app) == 0 and not app.get("audio")
    assert len([b for b in app.button if b.key.startswith("audio_")]) == 4
    boton(app).click().run()
    assert not app.exception and llamadas(app) == 1
    assert app.session_state.sim_ultimo_texto == "Chair"
    assert len(app.get("audio")) == 1
    assert not app.get("audio")[0].proto.autoplay
    boton(app).click().run()
    assert llamadas(app) == 1
    boton(app, "frase").click().run()
    assert not app.exception and llamadas(app) == 2
    assert app.session_state.sim_ultimo_texto == "This is a comfortable chair."
    # Enfocar otro objeto y redibujar no consulta TTS ni Gemini.
    next(b for b in app.button if "Enfocar #2" in b.label).click().run()
    assert not app.exception and llamadas(app) == 2
    assert len(app.get("audio")) == 1


@pytest.mark.parametrize("modo", ["Error", "Tiempo agotado"])
def test_error_no_bloquea_tarjetas_ni_expone_detalles(modo):
    app = iniciar()
    app.selectbox(key="sim_modo").select(modo).run()
    boton(app).click().run()
    assert not app.exception and llamadas(app) == 1
    assert app.warning and not app.get("audio")
    assert "datos privados" not in app.warning[0].value
    texto = " ".join(m.value for m in app.markdown)
    assert "Chair" in texto and "Table" in texto
    app.selectbox(key="sim_modo").select("Normal").run()
    boton(app).click().run()
    assert not app.exception and len(app.get("audio")) == 1


def test_dos_navegadores_demo_no_comparten_cache_ni_cierre():
    a, b = iniciar(), iniciar()
    assert a.session_state.usuario.sesion_id == b.session_state.usuario.sesion_id == "local_demo_session"
    assert a.session_state._audio_contexto.sesion_id != b.session_state._audio_contexto.sesion_id
    boton(a).click().run()
    boton(b).click().run()
    assert llamadas(a) == llamadas(b) == 1
    a.button(key="sim_cerrar").click().run()
    assert not a.exception and a.session_state.usuario is None
    assert "_audio_contexto" not in a.session_state
    assert len(audio._CACHE_AUDIO_SESION) == 1
    boton(b).click().run()
    assert llamadas(b) == 1


def test_expiracion_en_rerun_sin_sintesis_automatica(monkeypatch):
    reloj = Mock(return_value=100)
    monkeypatch.setattr(audio, "monotonic", reloj)
    app = iniciar()
    boton(app).click().run()
    assert len(app.get("audio")) == 1
    reloj.return_value = 1000000
    app.run()
    assert not app.exception and not app.get("audio")
    assert llamadas(app) == 1
    boton(app).click().run()
    assert llamadas(app) == 2


def test_cambio_usuario_no_reproduce_datos_anteriores():
    app = iniciar()
    boton(app).click().run()
    from uuid import uuid4
    app.session_state.usuario = replace(app.session_state.usuario, user_id=uuid4())
    app.run()
    assert not app.exception and not app.get("audio")
    assert not audio._CACHE_AUDIO_SESION
    assert not [b for b in app.button if b.key.startswith("audio_")]


def test_cierre_durante_error_revocacion_limpia_audio(monkeypatch):
    from homelens import acceso
    app = iniciar()
    boton(app).click().run()
    monkeypatch.setattr(acceso, "cerrar_sesion", Mock(side_effect=RuntimeError("revocación fallida")))
    app.button(key="sim_cerrar").click().run()
    assert app.exception  # M1 existente propaga el error; M5 descarta el audio igualmente.
    assert not audio._CACHE_AUDIO_SESION
    assert "_audio_contexto" not in app.session_state


def selector_velocidad(app, numero=0):
    return [r for r in app.radio if r.key and r.key.endswith("_velocidad")][numero]


def test_velocidad_predeterminada_es_lenta_y_palabra_es_normal(sin_red):
    app = iniciar()
    # 1. Escuchar palabra utiliza velocidad normal 1.0
    boton(app, "palabra").click().run()
    assert not app.exception
    assert app.session_state.sim_ultimo_texto == "Chair"
    assert app.session_state.sim_ultima_velocidad == 1.0
    assert len(app.get("audio")) == 1

    # 2. Escuchar frase utiliza velocidad lenta 0.8 por defecto
    boton(app, "frase").click().run()
    assert not app.exception
    assert app.session_state.sim_ultimo_texto == "This is a comfortable chair."
    assert app.session_state.sim_ultima_velocidad == 0.8
    assert len(app.get("audio")) == 1


def test_tres_velocidades_frase_y_reutilizacion_cache(sin_red):
    app = iniciar()

    # Opción 1: Lenta (0.8x) predeterminada
    boton(app, "frase").click().run()
    assert not app.exception and llamadas(app) == 1
    assert app.session_state.sim_ultima_velocidad == 0.8

    # Opción 2: Cambiar a Normal (1.0x)
    selector_velocidad(app).set_value("Normal (1.0x)").run()
    boton(app, "frase").click().run()
    assert not app.exception and llamadas(app) == 2
    assert app.session_state.sim_ultima_velocidad == 1.0

    # Opción 3: Cambiar a Muy lenta (0.65x)
    selector_velocidad(app).set_value("Muy lenta (0.65x)").run()
    boton(app, "frase").click().run()
    assert not app.exception and llamadas(app) == 3
    assert app.session_state.sim_ultima_velocidad == 0.65

    # Volver a Normal (1.0x) recupera desde la caché existente sin sintetizar otra vez
    selector_velocidad(app).set_value("Normal (1.0x)").run()
    boton(app, "frase").click().run()
    assert not app.exception and llamadas(app) == 3
    assert len(app.get("audio")) == 1


def test_seleccion_velocidad_se_mantiene_entre_tarjetas(sin_red):
    app = iniciar()
    assert selector_velocidad(app, 0).value == "Lenta (0.8x)"
    assert selector_velocidad(app, 1).value == "Lenta (0.8x)"

    # Cambiar velocidad en tarjeta 1
    selector_velocidad(app, 0).set_value("Muy lenta (0.65x)").run()
    # Tarjeta 2 debe reflejar la misma selección sincronizada
    assert selector_velocidad(app, 1).value == "Muy lenta (0.65x)"

    # Al pedir frase en tarjeta 2, se sintetiza a 0.65x
    boton(app, "frase", numero=1).click().run()
    assert not app.exception
    assert app.session_state.sim_ultimo_texto == "The table is next to the chair."
    assert app.session_state.sim_ultima_velocidad == 0.65


def test_etiquetas_idioma_reemplazan_emojis_de_bandera():
    app = iniciar()
    markdown_total = " ".join(m.value for m in app.markdown)
    # Ningún emoji de bandera debe figurar en las tarjetas educativas
    assert "🇬🇧" not in markdown_total
    assert "🇪🇸" not in markdown_total
    # Etiquetas textuales estilizadas deben estar presentes
    assert "EN · US" in markdown_total
    assert "ES" in markdown_total
