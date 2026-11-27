"""Componente de interfaz para la pantalla «Mi Progreso» (M8 - Parte 14).

Muestra los indicadores generales, los resultados desglosados por actividad
(Cuestionarios y Find It) y las vistas de vocabulario explorado y practicado
para el usuario con sesión activa (autenticado con Google o modo demo).
"""

from __future__ import annotations
import html
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import streamlit as st

from homelens.config import Configuracion
from homelens.datos.repositorio import RepositorioHomeLens
from homelens.modelos import (
    ContextoUsuario,
    EstadoPalabra,
    PalabraResumen,
    ResumenProgreso,
)
from homelens.progreso import obtener_progreso
from homelens.ui.estado import inicializar_estado_sesion

try:
    _TZ_ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")
except ZoneInfoNotFoundError:
    _TZ_ARGENTINA = timezone(timedelta(hours=-3), name="ART")


def _formatear_fecha_practica(dt: Optional[datetime]) -> str:
    """Formatea la fecha de última práctica en hora de Argentina (ART)."""
    if dt is None:
        return "Sin práctica registrada"
    fecha_utc = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return fecha_utc.astimezone(_TZ_ARGENTINA).strftime("%d/%m/%Y · %H:%M ART")


def formatear_porcentaje_aciertos(porcentaje: Optional[float]) -> str:
    """Formatea el porcentaje de aciertos diferenciando None de un 0 % real."""
    if porcentaje is None:
        return "Sin intentos evaluables"
    val = round(float(porcentaje), 2)
    if val == 0.0:
        return "0 %"
    if val.is_integer():
        return f"{int(val)} %"
    return f"{val:g} %"


def _renderizar_lista_vocabulario(
    palabras: List[PalabraResumen],
    mensaje_vacio: str,
) -> None:
    """Renderiza una lista de palabras en inglés y español adaptable a pantallas estrechas."""
    if not palabras:
        st.info(mensaje_vacio)
        return

    for palabra in palabras:
        en_esc = html.escape(palabra.nombre_en)
        es_esc = html.escape(palabra.nombre_es)
        es_practicada = palabra.estado == EstadoPalabra.PRACTICADA

        if es_practicada:
            badge_estado = (
                "<span class='hl-progreso-badge hl-badge-practicada'>"
                "✅ Practicada</span>"
            )
            detalle_practica = (
                f"<span class='hl-progreso-fecha'>Última práctica: "
                f"{html.escape(_formatear_fecha_practica(palabra.ultima_practica))}</span>"
            )
        else:
            badge_estado = (
                "<span class='hl-progreso-badge hl-badge-explorada'>"
                "📖 Explorada</span>"
            )
            detalle_practica = (
                "<span class='hl-progreso-fecha'>Pendiente de práctica</span>"
            )

        st.markdown(
            f"""
            <div class="hl-vocab-card">
                <div class="hl-vocab-main">
                    <span class="hl-lang-tag hl-lang-en">EN · US</span>
                    <span class="hl-vocab-en">{en_esc}</span>
                    <span class="hl-vocab-sep">/</span>
                    <span class="hl-lang-tag hl-lang-es">ES</span>
                    <span class="hl-vocab-es">{es_esc}</span>
                </div>
                <div class="hl-vocab-meta">
                    {badge_estado}
                    {detalle_practica}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def renderizar_pantalla_progreso(
    config: Optional[Configuracion] = None,
    repositorio: Optional[RepositorioHomeLens] = None,
) -> None:
    """Renderiza la vista «Mi Progreso» consumiendo obtener_progreso."""
    inicializar_estado_sesion()

    st.header("📊 Mi Progreso")
    st.caption(
        "Resumen de tu vocabulario en inglés y resultados de práctica en Cuestionarios y Find It."
    )

    usuario: Optional[ContextoUsuario] = st.session_state.get("usuario")
    if usuario is None:
        st.warning("🔒 Inicia sesión para consultar tu progreso de aprendizaje.")
        return

    if repositorio is not None:
        resultado = obtener_progreso(usuario, repositorio=repositorio, config=config)
    else:
        resultado = obtener_progreso(usuario, config=config)

    # 1. Caso de error en la consulta: diferenciar de cuenta vacía
    if not resultado.ok or resultado.valor is None:
        mensaje_err = (
            resultado.error.mensaje_usuario
            if resultado.error and resultado.error.mensaje_usuario
            else "No se pudo consultar tu progreso en este momento."
        )
        st.error(f"❌ {mensaje_err}")
        if resultado.error is None or resultado.error.reintentable:
            if st.button(
                "🔄 Reintentar",
                type="primary",
                key="btn_reintentar_progreso",
            ):
                st.rerun()
        return

    resumen: ResumenProgreso = resultado.valor
    datos = resumen.resultados_por_tipo

    # Estilos adaptables para escritorio y pantallas móviles estrechas
    st.markdown(
        """
        <style>
        .hl-vocab-card {
            border: 1px solid rgba(148, 163, 184, 0.35);
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 10px;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 8px 14px;
            background-color: rgba(248, 250, 252, 0.65);
        }
        .hl-vocab-main {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 6px;
            min-width: 0;
            word-break: break-word;
        }
        .hl-vocab-en {
            font-size: 1.08rem;
            font-weight: 700;
            color: #0f172a;
        }
        .hl-vocab-es {
            font-size: 1.0rem;
            color: #334155;
        }
        .hl-vocab-sep {
            color: #94a3b8;
            margin: 0 2px;
        }
        .hl-lang-tag {
            font-size: 0.68rem;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            color: #ffffff;
            letter-spacing: 0.04em;
            display: inline-block;
        }
        .hl-lang-en { background-color: #1d4ed8; }
        .hl-lang-es { background-color: #475569; }
        .hl-vocab-meta {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
        }
        .hl-progreso-badge {
            font-size: 0.78rem;
            font-weight: 600;
            padding: 3px 9px;
            border-radius: 999px;
            display: inline-block;
        }
        .hl-badge-practicada {
            background-color: #dcfce7;
            color: #166534;
        }
        .hl-badge-explorada {
            background-color: #e0f2fe;
            color: #075985;
        }
        .hl-progreso-fecha {
            font-size: 0.82rem;
            color: #64748b;
        }
        @media (max-width: 640px) {
            .hl-vocab-card {
                flex-direction: column;
                align-items: flex-start;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 2. Tres indicadores superiores principales
    col_ind1, col_ind2, col_ind3 = st.columns(3)
    with col_ind1:
        st.metric("Palabras exploradas", resumen.total_palabras_exploradas)
    with col_ind2:
        st.metric("Palabras practicadas", resumen.total_palabras_practicadas)
    with col_ind3:
        st.metric("Intentos registrados", resumen.total_intentos)

    # 3. Cuenta sin actividad: guiar al estudiante para comenzar
    if not resumen.tiene_actividad:
        st.info(
            "🌱 **Tu cuenta aún no registra actividad.**\n\n"
            "Para comenzar a construir tu progreso:\n"
            "- Ve a **Exploración Visual**, analiza una fotografía de tu hogar y presiona **Guardar** para registrar nuevas palabras y responder cuestionarios.\n"
            "- O participa directamente en **Desafíos Find It** buscando objetos cotidianos con tu cámara."
        )
        col_ir_exp, col_ir_fi = st.columns(2)
        with col_ir_exp:
            if st.button(
                "📸 Ir a Exploración Visual",
                use_container_width=True,
                key="btn_ir_exploracion_desde_progreso",
            ):
                st.session_state.seccion_navegacion = "Exploración Visual"
                st.rerun()
        with col_ir_fi:
            if st.button(
                "🎯 Ir a Desafíos Find It",
                use_container_width=True,
                key="btn_ir_find_it_desde_progreso",
            ):
                st.session_state.seccion_navegacion = "Desafíos Find It"
                st.rerun()
        return

    st.divider()

    # 4. Resultados desglosados por actividad: Cuestionarios y Find It
    st.subheader("🎯 Resultados por actividad")
    col_cuest, col_find = st.columns(2)

    with col_cuest:
        with st.container(border=True):
            st.markdown("#### 📝 Cuestionarios")
            c_corr = int(datos.get("cuestionarios_correctos", 0))
            c_inc = int(datos.get("cuestionarios_incorrectos", 0))
            c_pct = formatear_porcentaje_aciertos(
                resumen.porcentaje_aciertos_cuestionarios
            )

            m1, m2 = st.columns(2)
            with m1:
                st.metric("Respuestas correctas", c_corr)
            with m2:
                st.metric("Respuestas incorrectas", c_inc)
            st.metric("Porcentaje de aciertos (Cuestionarios)", c_pct)

    with col_find:
        with st.container(border=True):
            st.markdown("#### 🔎 Desafíos Find It")
            f_enc = int(datos.get("find_it_encontrados", 0))
            f_no_enc = int(datos.get("find_it_no_encontrados", 0))
            f_ind = int(datos.get("find_it_indeterminables", 0))
            f_pct = formatear_porcentaje_aciertos(
                resumen.porcentaje_aciertos_find_it
            )

            f1, f2, f3 = st.columns(3)
            with f1:
                st.metric("Encontrados", f_enc)
            with f2:
                st.metric("No encontrados", f_no_enc)
            with f3:
                st.metric("Indeterminables", f_ind)
            st.metric("Porcentaje de aciertos (Find It)", f_pct)
            st.caption(
                "Los intentos indeterminables tienen su propio conteo y no se descuentan como errores."
            )

    st.divider()

    # 5. Vocabulario en inglés y español (Exploradas vs Practicadas)
    st.subheader("📚 Vocabulario en inglés y español")

    no_resueltos = int(datos.get("objetos_no_resueltos_count", 0))
    if no_resueltos > 0:
        st.info(
            "ℹ️ Algunos intentos cuentan en tus resultados, pero su palabra no está disponible."
        )

    exploradas = resumen.palabras_exploradas
    practicadas = resumen.palabras_practicadas

    tab_exploradas, tab_practicadas = st.tabs(
        [
            f"📖 Exploradas ({len(exploradas)})",
            f"🎯 Practicadas ({len(practicadas)})",
        ]
    )

    with tab_exploradas:
        st.caption(
            "Palabras descubiertas en tus fotografías guardadas en el historial."
        )
        _renderizar_lista_vocabulario(
            exploradas,
            "Todavía no tienes palabras exploradas guardadas en tu historial.",
        )

    with tab_practicadas:
        st.caption(
            "Palabras con práctica evaluable en cuestionarios o desafíos Find It (incluye vocabulario del catálogo base)."
        )
        _renderizar_lista_vocabulario(
            practicadas,
            "Todavía no registras palabras con práctica evaluable.",
        )
