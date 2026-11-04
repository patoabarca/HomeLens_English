"""Vista aislada de M5: objetos fijos y MP3 silencioso; nunca usa servicios externos.

Ejecutar desde la raíz: python -m streamlit run scripts/prueba_audio_simulado.py
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from homelens.integraciones.tts import AdaptadorTTS
from homelens.modelos import (
    ContextoUsuario, Exploracion, ObjetoEducativo, RecuadroNormalizado, EstadoAnalisis,
)
from homelens.ui.audio import limpiar_audio_sesion_ui
from homelens.ui.estado import inicializar_estado_sesion, cerrar_sesion_usuario
from homelens.ui.exploracion import mostrar_exploracion


class ClienteSimulado:
    """Devuelve un MP3 de silencio reproducible, sin red ni credenciales."""

    def synthesize_speech(self, **kwargs):
        st.session_state["sim_llamadas"] = st.session_state.get("sim_llamadas", 0) + 1
        st.session_state["sim_ultimo_texto"] = kwargs["input"].text
        modo = st.session_state.get("sim_modo", "Normal")
        if modo == "Error":
            raise RuntimeError("Error simulado: datos privados que no deben mostrarse")
        if modo == "Tiempo agotado":
            raise TimeoutError("Tiempo agotado simulado")
        mp3 = Path(__file__).resolve().parents[1] / "tests/fixtures/audio_simulado.mp3"
        return SimpleNamespace(audio_content=mp3.read_bytes())


def main():
    st.set_page_config(page_title="HomeLens · prueba de audio", layout="wide")
    inicializar_estado_sesion()
    st.title("HomeLens English · prueba de audio")
    st.info("Simulación sin servicios externos. El MP3 contiene silencio de prueba, no una pronunciación.")
    if "sim_iniciado" not in st.session_state:
        st.session_state.sim_iniciado = True
        st.session_state.usuario = ContextoUsuario(
            UUID("00000000-0000-0000-0000-000000000001"), "local_demo_session", es_demo=True,
        )
    if st.session_state.usuario is None:
        st.success("Sesión simulada cerrada; audio descartado.")
        return
    if st.session_state.exploracion_actual is None:
        eid = uuid4()
        st.session_state.exploracion_actual = Exploracion(
            eid, st.session_state.usuario.user_id, datetime.now(timezone.utc),
            EstadoAnalisis.UTILIZABLE,
            objetos=[ObjetoEducativo(
                uuid4(), eid, "Chair", "Silla", RecuadroNormalizado(100, 100, 500, 500),
                "This is a comfortable chair.", "Esta es una silla cómoda.",
            ), ObjetoEducativo(
                uuid4(), eid, "Table", "Mesa", RecuadroNormalizado(500, 500, 900, 900),
                "The table is next to the chair.", "La mesa está al lado de la silla.",
            )],
        )
    with st.sidebar:
        st.subheader("Controles de prueba")
        st.selectbox("Respuesta simulada", ["Normal", "Error", "Tiempo agotado"], key="sim_modo")
        if st.button("Limpiar audio simulado", key="sim_limpiar"):
            limpiar_audio_sesion_ui()
        if st.button("Cerrar sesión simulada", key="sim_cerrar"):
            cerrar_sesion_usuario()
            st.rerun()
        st.caption("Cambiar el modo no borra la caché; límpiala para probar un error.")
    with patch("homelens.audio._crear_adaptador", return_value=AdaptadorTTS(cliente=ClienteSimulado())):
        mostrar_exploracion(st.session_state.exploracion_actual)
    st.caption(f"Solicitudes al cliente simulado: {st.session_state.get('sim_llamadas', 0)}")


if __name__ == "__main__":
    main()
