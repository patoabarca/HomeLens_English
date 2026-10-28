"""Componente de interfaz para el acceso de usuarios (M1).

Presenta la pantalla de bienvenida, el inicio de sesión mediante Google (Supabase Auth),
el modo demostración controlado para desarrollo local y el manejo de mensajes de error y expiración.
"""

from __future__ import annotations
import streamlit as st

from homelens.config import Configuracion
from homelens.acceso import iniciar_acceso, iniciar_acceso_demo


def renderizar_pantalla_acceso(config: Configuracion) -> None:
    """Renderiza la pantalla de ingreso y autenticación con Google.

    Args:
        config: Objeto de configuración activa del sistema.
    """
    # 1. Mensajes informativos de estado (cierre de sesión, expiración o retorno)
    if st.session_state.get("mensaje_auth"):
        st.info(f"ℹ️ {st.session_state.mensaje_auth}")
        st.session_state.mensaje_auth = None

    if st.session_state.get("error_auth"):
        st.error(f"❌ {st.session_state.error_auth}")
        st.session_state.error_auth = None

    # 2. Encabezado de bienvenida y propuesta pedagógica
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 25px;">
            <h1 style="margin-bottom: 5px;">🔍 HomeLens English</h1>
            <p style="font-size: 1.15em; color: #4B5563;">
                Aprende inglés explorando los objetos cotidianos de tu hogar con Inteligencia Artificial.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    with col_centro:
        with st.container(border=True):
            st.subheader("🔐 Accede a tu Espacio Personal")
            st.markdown(
                """
                Inicia sesión para descubrir objetos en tus fotografías, interactuar con tarjetas
                educativas y llevar un seguimiento de tu aprendizaje.
                """
            )

            st.divider()

            # Opción principal: Autenticación con Google a través de Supabase Auth
            if config.tiene_supabase:
                res_acceso = iniciar_acceso(
                    retorno_permitido=config.auth_redirect_url,
                    config=config,
                )

                if res_acceso.ok and res_acceso.valor is not None:
                    url_google = res_acceso.valor.url_autorizacion
                    st.link_button(
                        "🔑 Ingresar con Google",
                        url=url_google,
                        type="primary",
                        use_container_width=True,
                        help="Inicia sesión de forma segura a través de Google y Supabase Auth",
                    )
                    st.caption("🔒 Autenticación delegada segura mediante OAuth 2.0 y PKCE. No guardamos contraseñas.")
                else:
                    error_msg = res_acceso.error.mensaje_usuario if res_acceso.error else "Error al iniciar OAuth."
                    st.error(f"⚠️ {error_msg}")
            else:
                st.warning("⚠️ **Autenticación con Google pendiente de configuración**")
                st.markdown(
                    """
                    Para habilitar el ingreso con Google, se deben configurar las variables
                    `SUPABASE_URL` y `SUPABASE_ANON_KEY` en el archivo `.env`.
                    """
                )

            # Opción secundaria: Modo demostración local (exclusivo para desarrollo)
            if config.permitir_demo_local:
                st.divider()
                with st.expander("🧪 Modo Demostración Local (Solo Desarrollo)", expanded=False):
                    st.info(
                        "Este modo permite a los evaluadores y desarrolladores probar la aplicación localmente "
                        "sin credenciales de Supabase. No constituye una sesión personal real."
                    )
                    if st.button("🧪 Entrar como Usuario Demo", use_container_width=True):
                        res_demo = iniciar_acceso_demo(config=config)
                        if res_demo.ok and res_demo.valor:
                            st.session_state.usuario = res_demo.valor
                            st.session_state.mensaje_auth = "Sesión de demostración local iniciada."
                            st.rerun()
                        else:
                            st.error(res_demo.error.mensaje_usuario if res_demo.error else "Error en modo demo.")

    # 3. Avisos sobre privacidad y tratamiento seguro
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔒 Privacidad, Seguridad y Protección de Datos", expanded=False):
        st.markdown(
            """
            - **Identidad Estable:** Tu cuenta de Google se asocia a un identificador seguro único mediante Supabase Auth.
            - **Protección de Credenciales:** La aplicación no almacena contraseñas ni expone claves secretas en el navegador.
            - **Tratamiento Temporal de Imágenes:** Tus fotografías se procesan exclusivamente en memoria volátil de sesión y **nunca** se guardan en la base de datos ni en el servidor.
            - **Cierre Seguro:** Al cerrar tu sesión, todos los datos temporales, selecciones y fotografías en memoria se descartan de inmediato.
            """
        )
