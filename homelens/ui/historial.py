"""Componente de interfaz para el Historial de Exploraciones (M7).

Permite consultar exploraciones previamente guardadas por el usuario,
recuperar el vocabulario y actividades educativas sin consultar a Gemini
y gestionar el aislamiento de sesiones reales y modo demostración.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import streamlit as st

from homelens.config import Configuracion
from homelens.datos.supabase import RepositorioSupabase
from homelens.ui.exploracion import mostrar_exploracion

try:
    _TZ_ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")
except ZoneInfoNotFoundError:
    _TZ_ARGENTINA = timezone(timedelta(hours=-3), name="ART")


def formatear_fecha_local(creada_en: datetime) -> str:
    """Convierte una fecha/hora (asumiendo UTC si es naive) a hora local de Argentina (ART)."""
    fecha_utc = creada_en if creada_en.tzinfo is not None else creada_en.replace(tzinfo=timezone.utc)
    fecha_local = fecha_utc.astimezone(_TZ_ARGENTINA)
    return fecha_local.strftime("%d/%m/%Y — %H:%M ART")


def renderizar_pantalla_historial(config: Configuracion) -> None:
    """Renderiza la pantalla del historial privado de exploraciones."""
    usuario = st.session_state.get("usuario")
    if usuario is None:
        st.session_state.exploracion_en_vista_historial = None
        st.warning("🔒 Debes iniciar sesión para acceder a tu historial de exploraciones.")
        return

    # Descartar de inmediato cualquier detalle en vista perteneciente a otro usuario
    exp_previa = st.session_state.get("exploracion_en_vista_historial")
    if exp_previa is not None and exp_previa.user_id != usuario.user_id:
        st.session_state.exploracion_en_vista_historial = None

    st.header("📚 Mi Historial de Exploraciones")
    st.caption("Consulta tus exploraciones anteriores y repasa el vocabulario aprendido.")

    # Mensajes de estado
    if st.session_state.get("mensaje_historial"):
        st.success(f"ℹ️ {st.session_state.mensaje_historial}")
        st.session_state.mensaje_historial = None
    if st.session_state.get("error_historial"):
        st.error(f"❌ {st.session_state.error_historial}")
        st.session_state.error_historial = None

    # Advertencia informativa en modo demo
    if usuario.es_demo:
        st.info(
            "🧪 **Modo Demostración:** Las exploraciones de prueba se almacenan exclusivamente "
            "en la memoria de esta sesión de navegador y se borrarán al cerrar la sesión."
        )

    # Instanciación del repositorio asegurando aislamiento de sesión
    repo = RepositorioSupabase(
        supabase_url=config.supabase_url if config.tiene_supabase else None,
        anon_key=config.supabase_anon_key if config.tiene_supabase else None,
        almacen_demo=st.session_state.get("_exploraciones_demo"),
    )

    res_listado = repo.listar_exploraciones(usuario=usuario, limite=30)
    if not res_listado.ok:
        st.error(f"❌ {res_listado.error.mensaje_usuario if res_listado.error else 'Error al cargar el historial.'}")
        return

    exploraciones = res_listado.valor or []

    if not exploraciones:
        st.divider()
        st.info("ℹ️ **Aún no tienes exploraciones guardadas en tu historial.**")
        st.markdown(
            """
            Cuando tomes o cargues una fotografía en **'Exploración Visual'** y la analices con Gemini,
            presiona el botón **'💾 Guardar'** para conservarla en tu colección personal.
            """
        )
        return

    st.markdown(f"**Total de exploraciones guardadas:** `{len(exploraciones)}`")
    st.divider()

    # Listado de exploraciones en tarjetas ordenadas cronológicamente
    for exp in exploraciones:
        fecha_str = formatear_fecha_local(exp.creada_en)
        vocabulario_str = ", ".join(exp.titulos_objetos) if exp.titulos_objetos else "Sin objetos detectados"

        with st.container(border=True):
            col_info, col_accion = st.columns([3, 1])

            with col_info:
                st.markdown(f"📅 **Fecha:** `{fecha_str}`")
                st.markdown(f"🏷️ **Objetos ({exp.cantidad_objetos}):** *{vocabulario_str}*")

            with col_accion:
                if st.button("📖 Recuperar", key=f"btn_recuperar_{exp.exploracion_id}", use_container_width=True):
                    res_recuperar = repo.obtener_exploracion(usuario=usuario, exploracion_id=exp.exploracion_id)
                    if res_recuperar.ok and res_recuperar.valor is not None:
                        # Limpiar cualquier fotografía temporal activa para no mezclar imágenes
                        st.session_state.imagen_cargada_bytes = None
                        st.session_state.imagen_preparada = None
                        st.session_state.imagen_asociada_id = None
                        st.session_state.objeto_seleccionado_id = None

                        # Asignar la exploración recuperada como activa y marcarla como guardada
                        guardadas = st.session_state.get("exploraciones_guardadas_ids", set())
                        guardadas.add(res_recuperar.valor.exploracion_id)
                        st.session_state.exploraciones_guardadas_ids = guardadas
                        st.session_state.exploracion_actual = res_recuperar.valor
                        st.session_state.exploracion_en_vista_historial = res_recuperar.valor
                        st.toast("✅ Exploración recuperada con éxito.")
                        st.rerun()
                    else:
                        st.error(
                            res_recuperar.error.mensaje_usuario
                            if res_recuperar.error
                            else "No fue posible recuperar la exploración."
                        )

    # Vista detallada de la exploración actualmente seleccionada (verificando pertenencia)
    exp_detalle = st.session_state.get("exploracion_en_vista_historial")
    if exp_detalle is not None and exp_detalle.user_id != usuario.user_id:
        st.session_state.exploracion_en_vista_historial = None
        exp_detalle = None
    if exp_detalle is not None:
        st.divider()
        col_det_titulo, col_det_cerrar = st.columns([3, 1])
        with col_det_titulo:
            st.subheader("🔍 Contenido de la Exploración Recuperada")
            st.caption(f"ID: `{exp_detalle.exploracion_id}` — Creada el {formatear_fecha_local(exp_detalle.creada_en)}")
        with col_det_cerrar:
            if st.button("❌ Cerrar detalle", use_container_width=True):
                st.session_state.exploracion_en_vista_historial = None
                st.rerun()

        # Renderizar tarjetas pedagógicas de vocabulario (imagen=None indica que la foto temporal expiró)
        mostrar_exploracion(exploracion=exp_detalle, imagen=None)

