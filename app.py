"""HomeLens English - Aplicación Principal.

Punto de entrada de Streamlit y orquestación de módulos M0-M8.
Incluye autenticación delegada con Google vía Supabase Auth (M1 - Parte 5),
aislamiento de sesiones, protección de operaciones y navegación pedagógica.
"""

from __future__ import annotations
import streamlit as st

from homelens.config import cargar_configuracion
from homelens.acceso import obtener_usuario_actual, completar_acceso
from homelens.modelos import RespuestaAcceso
from homelens.ui.estado import inicializar_estado_sesion, cerrar_sesion_usuario
from homelens.ui.acceso import renderizar_pantalla_acceso
from homelens.ui.captura import renderizar_pantalla_captura


def main() -> None:
    st.set_page_config(
        page_title="HomeLens English",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inicializar_estado_sesion()

    # 1. Cargar configuración del sistema (M0)
    res_config = cargar_configuracion()
    if not res_config.ok or res_config.valor is None:
        st.error(f"Error de configuración: {res_config.error.mensaje_usuario if res_config.error else 'Desconocido'}")
        st.stop()

    config = res_config.valor

    # 2. Procesar retorno de OAuth (Google / Supabase) si existen parámetros en la URL
    params = st.query_params
    auth_code = params.get("code")
    auth_state = params.get("state") or st.session_state.get("auth_state")
    auth_error = params.get("error")
    auth_error_desc = params.get("error_description")

    if auth_code or auth_error:
        # Limpiar parámetros de la URL inmediatamente para no dejar credenciales temporales en el navegador
        st.query_params.clear()
        st.session_state.pop("auth_state", None)

        resp_acceso = RespuestaAcceso(
            code=auth_code,
            state=auth_state,
            error=auth_error,
            error_description=auth_error_desc,
        )
        res_comp = completar_acceso(
            respuesta_proveedor=resp_acceso,
            config=config,
            retorno_permitido=config.auth_redirect_url,
        )
        if res_comp.ok and res_comp.valor is not None:
            st.session_state.usuario = res_comp.valor
            st.session_state.mensaje_auth = (
                f"¡Bienvenido/a, {res_comp.valor.nombre or res_comp.valor.email or 'estudiante'}!"
            )
            st.session_state.error_auth = None
        else:
            st.session_state.usuario = None
            st.session_state.error_auth = (
                res_comp.error.mensaje_usuario if res_comp.error else "Error al completar el acceso con el proveedor."
            )
        st.rerun()

    # 3. Comprobar vigencia de la sesión en curso si existe usuario activo
    if st.session_state.get("usuario") is not None:
        sesion_actual_id = st.session_state.usuario.sesion_id
        res_verificacion = obtener_usuario_actual(
            sesion_id=sesion_actual_id,
            config=config,
        )
        if not res_verificacion.ok or res_verificacion.valor is None:
            # Sesión vencida o revocada en el proveedor: limpiar todo y notificar
            cerrar_sesion_usuario(config=config)
            st.session_state.error_auth = (
                res_verificacion.error.mensaje_usuario
                if res_verificacion.error
                else "Tu sesión ha expirado. Por favor, ingresa nuevamente con Google."
            )
            st.rerun()
        else:
            # Mantener contexto validado
            st.session_state.usuario = res_verificacion.valor

    usuario_autenticado = st.session_state.get("usuario") is not None

    # 4. Barra Lateral: Estado del Usuario, Navegación e Integraciones
    with st.sidebar:
        st.title("🔍 HomeLens English")
        st.caption("Aprende inglés explorando tu entorno con IA")
        st.divider()

        # Identificación del usuario en la barra lateral
        st.subheader("👤 Usuario")
        if usuario_autenticado:
            usr = st.session_state.usuario
            nombre_etiqueta = usr.nombre or usr.email or "Usuario Autenticado"
            st.write(f"**Identidad:** `{nombre_etiqueta}`")
            if usr.email and usr.email != nombre_etiqueta:
                st.caption(f"📧 {usr.email}")

            if usr.es_demo:
                st.warning("🧪 Modo Demostración Local")
            else:
                st.success("🟢 Sesión Google verificada")

            if st.button("🚪 Cerrar sesión", use_container_width=True):
                cerrar_sesion_usuario(config=config)
                st.rerun()
        else:
            st.info("🔒 **Sin sesión activa**")
            st.caption("Ingresa con Google para acceder a las funciones de aprendizaje.")

        st.divider()

        # Control de navegación: sólo accesible si el usuario está autenticado
        if usuario_autenticado:
            opciones_navegacion = [
                "Inicio / Estado",
                "Exploración Visual",
                "Prácticas y Cuestionarios",
                "Desafíos Find It",
                "Mi Progreso",
            ]
        else:
            opciones_navegacion = ["Acceso / Ingreso"]

        seccion = st.radio(
            "Navegación",
            opciones_navegacion,
            index=0,
        )

        st.divider()
        st.subheader("Estado de Integraciones")
        if usuario_autenticado:
            if st.session_state.usuario.es_demo:
                st.write("• **Acceso:** `🧪 Modo Demo (Desarrollo)`")
            else:
                st.write("• **Acceso:** `🟢 Google / Supabase Auth`")
        else:
            st.write("• **Acceso:** `🔴 No autenticado`")

        st.write(f"• **Entorno:** `{config.app_env}`")
        st.write(f"• **Gemini API:** {'🟢 Configurado' if config.tiene_gemini else '🟡 Pendiente (.env)'}")
        st.write(f"• **Supabase Auth:** {'🟢 Configurado' if config.tiene_supabase else '🟡 Pendiente (.env)'}")
        st.write(f"• **TTS Idioma:** `{config.google_tts_language_code}`")

        if st.session_state.get("imagen_preparada") is not None:
            st.divider()
            st.success("🖼️ Imagen activa en memoria")
            st.caption(f"{st.session_state.imagen_preparada.ancho}x{st.session_state.imagen_preparada.alto} px ({st.session_state.imagen_preparada.mime_type})")

    # 5. Contenido Principal según Estado de Autenticación
    if not usuario_autenticado:
        # Pantalla de acceso obligatoria: bloquea operaciones protegidas sin sesión válida
        renderizar_pantalla_acceso(config)
        return

    # Usuario debidamente autenticado
    if seccion == "Inicio / Estado":
        st.header("Bienvenido a HomeLens English")
        st.markdown(
            """
            **HomeLens English** transforma los objetos reales de tu entorno en oportunidades
            prácticas para aprender vocabulario y gramática en inglés.

            ### Estado del Sistema:
            - ✅ **M1 Acceso de usuarios:** Autenticación delegada con Google vía Supabase Auth y validación en servidor.
            - ✅ **M0 Configuración y Entorno:** Validado y cargado de forma segura sin exponer credenciales.
            - ✅ **M2 Captura y Preparación:** Validación estricta, orientación EXIF y memoria volátil segura.
            - ✅ **M3 Análisis con Gemini:** Detección multimodal de objetos y generación pedagógica estructurada.
            - ✅ **M4 Exploración Visual:** Recuadros normalizados con foco interactivo y tarjetas educativas.
            - ✅ **Aislamiento de Secretos:** Exclusión estricta en `.gitignore`, Docker reproducible y variables seguras.
            """
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Módulo Activo", value="M1 Acceso")
        with col2:
            st.metric(label="Límite Tamaño Imagen", value=f"{config.max_image_size_bytes // 1_000_000} MB")
        with col3:
            st.metric(label="Modelo Gemini", value=config.gemini_model)

    elif seccion == "Exploración Visual":
        renderizar_pantalla_captura(config)

    elif seccion == "Prácticas y Cuestionarios":
        st.header("📝 Prácticas y Cuestionarios")
        st.info("Los cuestionarios interactivos basados en tus exploraciones se activarán en las siguientes etapas.")

    elif seccion == "Desafíos Find It":
        st.header("🎯 Desafíos Find It")
        st.info("El módulo de desafíos interactivos por categoría se activará en las siguientes etapas.")

    elif seccion == "Mi Progreso":
        st.header("📊 Mi Progreso")
        st.info("Tu historial de palabras exploradas y estadísticas de práctica se mostrarán aquí.")


if __name__ == "__main__":
    main()
