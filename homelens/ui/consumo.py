"""Componente de interfaz para el Panel de Consumo de IA (Gemini).

Exclusivo para los creadores de HomeLens English (Patricia, Lucas, Victoria).
Permite monitorear el consumo de tokens, llamadas a la API y costos operativos
estimados sin exponer datos personales, credenciales ni alterar las vistas educativas.
"""

from __future__ import annotations
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

import streamlit as st
import pandas as pd
import altair as alt

from homelens.config import (
    Configuracion,
    es_creador_autorizado,
    obtener_nombre_creador,
)
from homelens.modelos import (
    ContextoUsuario,
    RegistroConsumoIA,
    FiltroConsumoIA,
    ResumenConsumoIA,
)
from homelens.datos.supabase import RepositorioSupabase
from homelens.costos import calcular_costo_gemini

try:
    _TZ_ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")
except ZoneInfoNotFoundError:
    _TZ_ARGENTINA = timezone(timedelta(hours=-3), name="ART")


def formatear_fecha_argentina(dt: datetime) -> str:
    """Convierte fecha UTC a hora local de Argentina en formato 'DD/MM/YYYY · HH:MM ART'."""
    fecha_utc = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return fecha_utc.astimezone(_TZ_ARGENTINA).strftime("%d/%m/%Y · %H:%M ART")


def calcular_resumen_consumo(registros: List[RegistroConsumoIA]) -> ResumenConsumoIA:
    """Calcula agregados y promedios para las tarjetas de KPI del panel.

    Reglas de cálculo:
    - Fotografías analizadas: solo operaciones con estado EXITO.
    - Solicitudes a la API: total de llamadas HTTP efectivamente realizadas (incluyendo reintentos).
    - Reintentos: reintentos ejecutados ante fallos transitorios.
    - Solicitudes fallidas: operaciones cuyo estado final no fue exitoso.
    - Tokens: suma de tokens totales conocidos (ignora valores no disponibles).
    - Costo acumulado: suma de costos estimados conocidos sin convertir faltantes en cero.
    - Costo promedio por foto: costo de fotografías exitosas dividido por la cantidad de fotos exitosas con costo.
    """
    fotos_exitosas = [r for r in registros if r.estado == "EXITO"]
    total_fotos = len(fotos_exitosas)
    total_solicitudes = sum(r.numero_llamadas for r in registros)
    total_reintentos = sum(r.numero_reintentos for r in registros)
    total_fallidas = sum(1 for r in registros if r.estado != "EXITO")

    tokens_validos = [r.total_tokens for r in registros if r.total_tokens is not None]
    total_tokens = sum(tokens_validos, 0)

    costos_validos = [r.costo_estimado for r in registros if r.costo_estimado is not None]
    costo_acumulado = sum(costos_validos, Decimal("0.000000"))

    # Costo promedio: se calcula exclusivamente sobre fotos exitosas con costo conocido
    fotos_con_costo = [r for r in fotos_exitosas if r.costo_estimado is not None]
    costo_fotos = sum((r.costo_estimado for r in fotos_con_costo), Decimal("0.000000"))

    costo_promedio: Optional[Decimal] = None
    if len(fotos_con_costo) > 0 and costo_fotos > Decimal("0"):
        costo_promedio = (costo_fotos / Decimal(len(fotos_con_costo))).quantize(Decimal("0.000001"))

    return ResumenConsumoIA(
        total_fotografias=total_fotos,
        total_solicitudes=total_solicitudes,
        total_reintentos=total_reintentos,
        total_solicitudes_fallidas=total_fallidas,
        total_tokens=total_tokens,
        costo_acumulado=costo_acumulado,
        costo_promedio_por_foto=costo_promedio,
    )


def generar_datos_simulados_consumo(config: Configuracion) -> List[RegistroConsumoIA]:
    """Genera un lote sintético de 12 operaciones para previsualización local sin llamadas a APIs.

    Incluye a los tres integrantes creadores de HomeLens English (Patricia, Lucas y Victoria)
    con casos reales de éxito, error, reintentos y tokens de razonamiento.
    """
    # Identificadores de los tres creadores
    uid_patricia = None
    uid_lucas = None
    uid_victoria = None
    for uid, nombre in config.creadores_autorizados.items():
        if nombre == "Patricia":
            uid_patricia = uid
        elif nombre == "Lucas":
            uid_lucas = uid
        elif nombre == "Victoria":
            uid_victoria = uid

    mapa_creadores: Dict[int, tuple[UUID, str]] = {
        0: (uid_patricia or UUID("11111111-1111-4111-8111-111111111111"), "Patricia"),
        1: (uid_lucas or UUID("22222222-2222-4222-8222-222222222222"), "Lucas"),
        2: (uid_victoria or UUID("33333333-3333-4333-8333-333333333333"), "Victoria"),
    }

    ahora = datetime.now(timezone.utc)
    datos_base = [
        # (dias_atras, creador_idx, estado, llamadas, reintentos, p_tok, c_tok, t_tok, cache_tok, cod_err)
        (0, 0, "EXITO", 1, 0, 1200, 350, 150, 0, None),     # Patricia hoy
        (0, 1, "EXITO", 1, 0, 1400, 420, 200, 500, None),   # Lucas hoy con caché
        (1, 2, "EXITO", 1, 0, 950, 280, 120, 0, None),      # Victoria ayer
        (1, 0, "EXITO", 2, 1, 1100, 310, 180, 0, None),     # Patricia ayer (1 reintento exitoso)
        (2, 1, "ERROR", 1, 0, None, None, None, 0, 402),     # Lucas error 402 sin tokens
        (2, 2, "EXITO", 1, 0, 1300, 390, 160, 0, None),     # Victoria hace 2 días
        (3, 0, "EXITO", 1, 0, 1600, 480, 220, 600, None),   # Patricia hace 3 días
        (3, 1, "EXITO", 1, 0, 1050, 300, 140, 0, None),     # Lucas hace 3 días
        (4, 2, "EXITO", 1, 0, 890, 260, 110, 0, None),      # Victoria hace 4 días
        (4, 0, "ERROR", 2, 1, None, None, None, 0, 503),     # Patricia error transitorio 503
        (5, 1, "EXITO", 1, 0, 1450, 410, 190, 400, None),   # Lucas hace 5 días
        (6, 2, "EXITO", 1, 0, 1250, 360, 170, 0, None),     # Victoria hace 6 días
    ]

    simulados: List[RegistroConsumoIA] = []
    for dias, c_idx, estado, llamadas, reintentos, p_tok, c_tok, t_tok, cache_tok, cod_err in datos_base:
        uid, nombre = mapa_creadores[c_idx]
        fecha_op = ahora - timedelta(days=dias, hours=c_idx * 2 + 1, minutes=15)
        calc = calcular_costo_gemini(
            modelo="gemini-3.6-flash",
            prompt_tokens=p_tok,
            candidates_tokens=c_tok,
            thoughts_tokens=t_tok,
            cached_tokens=cache_tok,
            fecha=fecha_op,
        )
        tot = (p_tok + c_tok + (t_tok or 0)) if (p_tok is not None and c_tok is not None) else None
        simulados.append(
            RegistroConsumoIA(
                id=uuid4(),
                operacion_id=uuid4(),
                user_id=uid,
                fecha=fecha_op,
                modelo="gemini-3.6-flash",
                estado=estado,
                duracion_ms=900 + (p_tok or 0) // 2,
                numero_llamadas=llamadas,
                numero_reintentos=reintentos,
                codigo_error=cod_err,
                prompt_tokens=p_tok,
                candidates_tokens=c_tok,
                thoughts_tokens=t_tok,
                total_tokens=tot,
                cached_tokens=cache_tok,
                tarifa_version=calc.tarifa_version,
                costo_estimado=calc.costo_estimado,
                integrante_etiqueta=nombre,
                metadatos=calc.desglose,
            )
        )
    return simulados


def renderizar_pantalla_consumo(
    config: Configuracion,
    repositorio: Optional[RepositorioSupabase] = None,
) -> None:
    """Renderiza el Panel de Consumo de IA con controles de acceso en el servidor."""
    usuario: Optional[ContextoUsuario] = st.session_state.get("usuario")

    # 1. Comprobación estricta de seguridad en el servidor
    if usuario is None:
        st.error("🔒 **Acceso Denegado:** Se requiere iniciar sesión con Google para acceder.")
        st.stop()

    if usuario.es_demo:
        st.error("🧪 **Acceso Restringido:** El Panel de Consumo no está disponible en el Modo Demostración.")
        st.stop()

    if not es_creador_autorizado(usuario, config):
        st.error("🚫 **Acceso Restringido:** Este panel es exclusivo para los creadores del proyecto (Patricia, Lucas y Victoria).")
        st.info("Tu cuenta autenticada no forma parte del equipo de creadores autorizados para visualizar métricas de costos.")
        st.stop()

    # Inyección de estilos visuales limpios, sobrios y profesionales
    st.markdown(
        """
        <style>
        /* Ajuste uniforme y profesional para tarjetas KPI */
        [data-testid="stMetric"] {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 14px 16px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
            min-height: 110px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            color: #475569 !important;
            margin-bottom: 2px;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.45rem !important;
            font-weight: 700 !important;
            color: #0F172A !important;
        }
        [data-testid="stMetricDelta"] {
            font-size: 0.75rem !important;
        }
        /* Contenedores de aviso de previsualización */
        .banner-preview-consumo {
            background-color: #EFF6FF;
            border-left: 4px solid #3B82F6;
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 16px;
        }
        .banner-preview-consumo strong {
            color: #1E40AF;
        }
        .banner-preview-consumo span {
            color: #1E3A8A;
            font-size: 0.92rem;
        }
        /* Cuadro de estado individual */
        .tarjeta-vista-individual {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 18px 20px;
            height: 230px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 2. Encabezado principal y notas técnicas
    st.header("📊 Panel de Consumo de Inteligencia Artificial")
    col_t1, col_t2 = st.columns([3, 1.2])
    with col_t1:
        st.caption("Monitoreo de telemetría, tokens y costos operativos de Google Gemini — MVP HomeLens English")
    with col_t2:
        modo_preview = st.toggle(
            "🧪 Datos Simulados",
            value=st.session_state.get("_preview_consumo_ficticio", False),
            key="_toggle_preview_consumo",
            help="Previsualiza gráficos y métricas con datos sintéticos para Patricia, Lucas y Victoria sin conectar a Supabase ni llamar a Gemini.",
        )
        st.session_state._preview_consumo_ficticio = modo_preview

    if modo_preview:
        st.markdown(
            """
            <div class="banner-preview-consumo">
                <strong>🧪 Modo Previsualización Activo:</strong>
                <span> Mostrando 12 operaciones sintéticas para Patricia, Lucas y Victoria. No se realizan llamadas a la API de Gemini ni escrituras en Supabase.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("ℹ️ Acerca de la estimación de costos y tarifas vigentes", expanded=False):
        st.markdown(
            """
            * **Costo estimado por HomeLens:** Calculado a partir de los metadatos oficiales de tokens (`usage_metadata`) retornados por la API de Gemini y las tarifas públicas de Google AI Studio.
            * **Costo real facturado por Google:** Importe definitivo auditado por Google Cloud Billing. La estimación interna no representa un saldo de billetera en tiempo real.
            * **Tarifas verificadas (Google Gemini Flash - gemini-3.6-flash):**
              * *Hasta 31/12/2026:*
                - Entrada estándar: **US$ 0,75** / M tokens ($0.00000075 / token).
                - Salida (respuesta + razonamiento): **US$ 3,75** / M tokens ($0.00000375 / token).
                - Lectura de caché de contexto: **US$ 0,075** / M tokens ($0.000000075 / token).
              * *Desde 01/01/2027:*
                - Entrada estándar: **US$ 1,50** / M tokens ($0.00000150 / token).
                - Salida (respuesta + razonamiento): **US$ 7,50** / M tokens ($0.00000750 / token).
                - Lectura de caché de contexto: **US$ 0,15** / M tokens ($0.00000015 / token).
            * **Fórmula de salida:** `tokens_salida_facturables = candidates_token_count + thoughts_token_count`.
            * **Almacenamiento de caché:** No aplicable en consultas puntuales de imágenes sin sesiones de caché de contexto con retención horaria explícita.
            """
        )

    # 3. Obtener repositorio e historial de consumo
    repo = repositorio
    if repo is None:
        repo = RepositorioSupabase(
            supabase_url=config.supabase_url,
            anon_key=config.supabase_anon_key,
        )

    # 4. Filtros interactivos en panel superior
    st.subheader("🔍 Filtros de Consulta")
    col_f1, col_f2, col_f3, col_f4 = st.columns([1.5, 1.2, 1.2, 1.5])

    # Opciones de integrantes: incluye a los tres creadores del proyecto
    opciones_integrantes = ["Todos los integrantes", "Patricia", "Lucas", "Victoria"]

    with col_f1:
        seleccion_integrante = st.selectbox(
            "👤 Integrante",
            options=opciones_integrantes,
            index=0,
            help="Filtra las operaciones por creador o visualiza la totalidad del equipo.",
        )

    with col_f2:
        filtro_modelo = st.selectbox(
            "🤖 Modelo",
            options=["Todos los modelos", "gemini-3.6-flash", "gemini-2.5-flash"],
            index=0,
            help="Filtra por modelo de lenguaje utilizado en el análisis.",
        )
        modelo_query = None if filtro_modelo == "Todos los modelos" else filtro_modelo

    with col_f3:
        filtro_estado = st.selectbox(
            "⚡ Estado",
            options=["Todos los estados", "Éxito", "Error"],
            index=0,
            help="Filtra según el resultado final de la operación de análisis.",
        )

    with col_f4:
        rango_fechas = st.date_input(
            "📅 Rango de Fechas",
            value=(date.today() - timedelta(days=30), date.today()),
            max_value=date.today(),
            help="Filtra por fecha en hora local de Argentina (ART).",
        )

    # Interpretación de fechas locales en Argentina (ART) convertidas a UTC
    fecha_desde_dt: Optional[datetime] = None
    fecha_hasta_dt: Optional[datetime] = None
    if isinstance(rango_fechas, tuple):
        if len(rango_fechas) >= 1 and rango_fechas[0]:
            dt_art_inicio = datetime.combine(rango_fechas[0], datetime.min.time(), tzinfo=_TZ_ARGENTINA)
            fecha_desde_dt = dt_art_inicio.astimezone(timezone.utc)
        if len(rango_fechas) >= 2 and rango_fechas[1]:
            dt_art_fin = datetime.combine(rango_fechas[1], datetime.max.time(), tzinfo=_TZ_ARGENTINA)
            fecha_hasta_dt = dt_art_fin.astimezone(timezone.utc)

    # Resolver UUID de creador si está seleccionado
    filtro_uid_query: Optional[UUID] = None
    if seleccion_integrante != "Todos los integrantes":
        for uid, nom in config.creadores_autorizados.items():
            if nom == seleccion_integrante:
                filtro_uid_query = uid
                break

    estado_query: Optional[str] = None
    if filtro_estado == "Éxito":
        estado_query = "EXITO"
    elif filtro_estado == "Error":
        estado_query = "ERROR"

    filtro = FiltroConsumoIA(
        user_id=filtro_uid_query,
        modelo=modelo_query,
        estado=estado_query,
        fecha_desde=fecha_desde_dt,
        fecha_hasta=fecha_hasta_dt,
    )

    # 5. Obtención de datos (Simulados o Supabase)
    if modo_preview:
        registros_crudos = generar_datos_simulados_consumo(config)
        registros: List[RegistroConsumoIA] = []
        for r in registros_crudos:
            if seleccion_integrante != "Todos los integrantes":
                if r.integrante_etiqueta != seleccion_integrante:
                    continue
            if modelo_query and r.modelo != modelo_query:
                continue
            if filtro_estado == "Éxito" and r.estado != "EXITO":
                continue
            if filtro_estado == "Error" and r.estado == "EXITO":
                continue
            if fecha_desde_dt and r.fecha < fecha_desde_dt:
                continue
            if fecha_hasta_dt and r.fecha > fecha_hasta_dt:
                continue
            registros.append(r)
    else:
        with st.spinner("Consultando registros de consumo en Supabase..."):
            res_consumo = repo.consultar_consumo_gemini(usuario=usuario, filtro=filtro)

        if not res_consumo.ok:
            st.error(f"❌ Error al consultar métricas: {res_consumo.error.mensaje_usuario if res_consumo.error else 'Error desconocido'}")
            return

        registros = res_consumo.valor or []

    # Estado vacío claro y elegante
    if not registros:
        st.divider()
        st.info("ℹ️ No se encontraron registros de consumo para los filtros seleccionados.")
        st.caption("Ajustá el rango de fechas o los filtros superiores para explorar otras operaciones.")
        if not modo_preview:
            if st.button("🧪 Activar datos simulados para previsualizar el panel"):
                st.session_state._preview_consumo_ficticio = True
                st.rerun()
        return

    resumen = calcular_resumen_consumo(registros)

    st.divider()

    # 6. Tarjetas de Indicadores Principales (KPIs)
    st.subheader("📌 Indicadores Principales")
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

    with kpi1:
        st.metric(
            label="📸 Fotos Analizadas",
            value=resumen.total_fotografias,
            help="Operaciones de análisis completadas exitosamente con respuesta educativa de Gemini.",
        )

    with kpi2:
        st.metric(
            label="📞 Solicitudes API",
            value=resumen.total_solicitudes,
            delta=f"{resumen.total_reintentos} reintentos" if resumen.total_reintentos > 0 else "0 reintentos",
            delta_color="off",
            help="Llamadas HTTP efectivamente realizadas a Gemini, incluyendo llamadas iniciales y reintentos.",
        )

    with kpi3:
        st.metric(
            label="🪙 Tokens Consumidos",
            value=f"{resumen.total_tokens:,}".replace(",", "."),
            help="Total acumulado de tokens de entrada (prompt), respuesta generada y razonamiento.",
        )

    with kpi4:
        st.metric(
            label="💵 Costo Acumulado",
            value=f"US$ {float(resumen.costo_acumulado):.4f}",
            help="Suma de los costos estimados conocidos calculados según tarifas oficiales por millón de tokens.",
        )

    with kpi5:
        promedio_str = f"US$ {float(resumen.costo_promedio_por_foto):.4f}" if resumen.costo_promedio_por_foto else "N/D"
        st.metric(
            label="🎯 Costo Prom./Foto",
            value=promedio_str,
            help="Costo acumulado dividido exclusivamente entre las fotografías analizadas con éxito con costo conocido.",
        )

    with kpi6:
        st.metric(
            label="⚠️ Solicitudes Fallidas",
            value=resumen.total_solicitudes_fallidas,
            delta="Operaciones con error" if resumen.total_solicitudes_fallidas > 0 else "0 errores",
            delta_color="inverse",
            help="Operaciones de análisis que finalizaron con error (ej. cuota excedida 429, facturación 402 o indisponibilidad 503).",
        )

    st.divider()

    # 7. Visualizaciones Gráficas
    st.subheader("📈 Evolución y Distribución del Consumo")

    # Preparar DataFrame para visualización
    datos_df = []
    for r in registros:
        costo_flt = float(r.costo_estimado) if r.costo_estimado is not None else 0.0
        costo_texto = f"US$ {float(r.costo_estimado):.6f}" if r.costo_estimado is not None else "N/D"
        fecha_art = r.fecha.astimezone(_TZ_ARGENTINA) if r.fecha.tzinfo else r.fecha
        datos_df.append(
            {
                "Fecha_Hora": formatear_fecha_argentina(r.fecha),
                "Fecha_Dia_Sort": fecha_art.strftime("%Y-%m-%d"),
                "Fecha_Corta": fecha_art.strftime("%d/%m"),
                "Fecha_Completa": fecha_art.strftime("%d/%m/%Y"),
                "Integrante": r.integrante_etiqueta or "Desconocido",
                "Modelo": r.modelo,
                "Estado_Tecnico": r.estado,
                "Estado_Display": "🟢 Éxito" if r.estado == "EXITO" else "🔴 Error",
                "Estado_Etiqueta": "Éxito" if r.estado == "EXITO" else "Error",
                "Llamadas": r.numero_llamadas,
                "Reintentos": r.numero_reintentos,
                "Entrada": r.prompt_tokens or 0,
                "Salida": r.candidates_tokens or 0,
                "Razonamiento": r.thoughts_tokens or 0,
                "Total_Tokens": r.total_tokens or 0,
                "Entrada_Display": str(r.prompt_tokens) if r.prompt_tokens is not None else "N/D",
                "Salida_Display": str(r.candidates_tokens) if r.candidates_tokens is not None else "N/D",
                "Razonamiento_Display": str(r.thoughts_tokens) if r.thoughts_tokens is not None else "N/D",
                "Total_Display": str(r.total_tokens) if r.total_tokens is not None else "N/D",
                "Costo_USD": costo_flt,
                "Costo_Texto": costo_texto,
                "Es_Exito": 1 if r.estado == "EXITO" else 0,
                "Es_Error": 1 if r.estado != "EXITO" else 0,
            }
        )

    df = pd.DataFrame(datos_df)

    # Gráficos fila 1: Costo diario (columnas) y Tokens diarios
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("**Costo Estimado Diario (US$)**")
        df_costo_dia = (
            df.groupby(["Fecha_Dia_Sort", "Fecha_Corta", "Fecha_Completa"], as_index=False)
            .agg(Costo_USD=("Costo_USD", "sum"), Operaciones=("Estado_Tecnico", "count"))
            .sort_values("Fecha_Dia_Sort")
        )
        df_costo_dia["Costo_Tooltip"] = df_costo_dia["Costo_USD"].apply(lambda v: f"US$ {v:.6f}")

        chart_costo = (
            alt.Chart(df_costo_dia)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#2563EB")
            .encode(
                x=alt.X("Fecha_Corta:N", sort=alt.SortField("Fecha_Dia_Sort", order="ascending"), axis=alt.Axis(title="Día (DD/MM)", labelAngle=0)),
                y=alt.Y("Costo_USD:Q", scale=alt.Scale(domainMin=0, zero=True), axis=alt.Axis(title="Costo Estimado (USD)", format="$.4f")),
                tooltip=[
                    alt.Tooltip("Fecha_Completa:N", title="Fecha"),
                    alt.Tooltip("Costo_Tooltip:N", title="Costo Estimado"),
                    alt.Tooltip("Operaciones:Q", title="Operaciones Registradas"),
                ],
            )
            .properties(height=230)
        )
        st.altair_chart(chart_costo, use_container_width=True)

    with col_g2:
        st.markdown("**Tokens Consumidos por Día**")
        df_tokens_dia = (
            df.groupby(["Fecha_Dia_Sort", "Fecha_Corta", "Fecha_Completa"], as_index=False)
            .agg(Total_Tokens=("Total_Tokens", "sum"), Operaciones=("Estado_Tecnico", "count"))
            .sort_values("Fecha_Dia_Sort")
        )
        df_tokens_dia["Tokens_Tooltip"] = df_tokens_dia["Total_Tokens"].apply(lambda v: f"{v:,}".replace(",", ".") + " tokens")

        chart_tokens = (
            alt.Chart(df_tokens_dia)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#4F46E5")
            .encode(
                x=alt.X("Fecha_Corta:N", sort=alt.SortField("Fecha_Dia_Sort", order="ascending"), axis=alt.Axis(title="Día (DD/MM)", labelAngle=0)),
                y=alt.Y("Total_Tokens:Q", scale=alt.Scale(domainMin=0, zero=True), axis=alt.Axis(title="Tokens Consumidos", format="~s")),
                tooltip=[
                    alt.Tooltip("Fecha_Completa:N", title="Fecha"),
                    alt.Tooltip("Tokens_Tooltip:N", title="Tokens Consumidos"),
                    alt.Tooltip("Operaciones:Q", title="Operaciones Registradas"),
                ],
            )
            .properties(height=230)
        )
        st.altair_chart(chart_tokens, use_container_width=True)

    # Gráficos fila 2: Distribución de éxito/error y Comparativa por integrante
    col_g3, col_g4 = st.columns(2)

    with col_g3:
        st.markdown("**Distribución de Operaciones (Éxito vs Error)**")
        df_estado = (
            df.groupby("Estado_Etiqueta", as_index=False)
            .agg(Cantidad=("Estado_Tecnico", "count"))
        )

        base_estado = alt.Chart(df_estado).encode(
            x=alt.X("Estado_Etiqueta:N", axis=alt.Axis(title="Resultado de la Operación", labelAngle=0)),
            y=alt.Y("Cantidad:Q", scale=alt.Scale(domainMin=0, zero=True), axis=alt.Axis(title="Cantidad de Operaciones", format="d")),
            color=alt.Color(
                "Estado_Etiqueta:N",
                scale=alt.Scale(domain=["Éxito", "Error"], range=["#10B981", "#EF4444"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("Estado_Etiqueta:N", title="Estado"),
                alt.Tooltip("Cantidad:Q", title="Operaciones"),
            ],
        )
        bars_estado = base_estado.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=60)
        text_estado = base_estado.mark_text(dy=-10, fontSize=13, fontWeight="bold", color="#1E293B").encode(
            text="Cantidad:Q"
        )
        chart_estado = (bars_estado + text_estado).properties(height=230)
        st.altair_chart(chart_estado, use_container_width=True)

    with col_g4:
        st.markdown("**Costo Estimado por Integrante (US$)**")
        if seleccion_integrante == "Todos los integrantes":
            df_integrante = (
                df.groupby("Integrante", as_index=False)
                .agg(Costo_USD=("Costo_USD", "sum"), Operaciones=("Estado_Tecnico", "count"))
            )
            df_integrante["Costo_Tooltip"] = df_integrante["Costo_USD"].apply(lambda v: f"US$ {v:.6f}")

            chart_integrante = (
                alt.Chart(df_integrante)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#0EA5E9")
                .encode(
                    x=alt.X("Integrante:N", axis=alt.Axis(title="Integrante del Equipo", labelAngle=0)),
                    y=alt.Y("Costo_USD:Q", scale=alt.Scale(domainMin=0, zero=True), axis=alt.Axis(title="Costo Acumulado (USD)", format="$.4f")),
                    tooltip=[
                        alt.Tooltip("Integrante:N", title="Integrante"),
                        alt.Tooltip("Costo_Tooltip:N", title="Costo Acumulado"),
                        alt.Tooltip("Operaciones:Q", title="Operaciones"),
                    ],
                )
                .properties(height=230)
            )
            st.altair_chart(chart_integrante, use_container_width=True)
        else:
            costo_filtrado = df["Costo_USD"].sum()
            ops_filtradas = len(df)
            ops_ok = sum(df["Es_Exito"])
            ops_err = sum(df["Es_Error"])
            st.markdown(
                f"""
                <div class="tarjeta-vista-individual">
                    <h4 style="margin: 0 0 10px 0; color: #1E293B; font-size: 1.05rem;">👤 Vista Individual: {seleccion_integrante}</h4>
                    <p style="margin: 0 0 6px 0; color: #475569; font-size: 0.95rem;">
                        Costo acumulado filtrado: <strong style="color: #0F172A;">US$ {costo_filtrado:.6f}</strong>
                    </p>
                    <p style="margin: 0 0 14px 0; color: #475569; font-size: 0.95rem;">
                        Operaciones registradas: <strong style="color: #0F172A;">{ops_filtradas}</strong> ({ops_ok} exitosas, {ops_err} con error)
                    </p>
                    <span style="color: #64748B; font-size: 0.85rem; font-style: italic;">
                        💡 La comparativa visual entre todos los integrantes está disponible seleccionando <strong>"Todos los integrantes"</strong> en los filtros superiores.
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # 8. Tabla Detallada de Operaciones
    st.subheader("📋 Registro Detallado de Operaciones")

    st.info(
        "ℹ️ **Interpretación del registro:** Cada fila representa una operación de análisis registrada, "
        "con su consumo de tokens, reintentos y costo estimado. Las llamadas individuales pueden ser mayores "
        "que las operaciones debido a los reintentos.",
        icon="ℹ️",
    )

    df_mostrar = df[
        [
            "Fecha_Hora",
            "Integrante",
            "Modelo",
            "Estado_Display",
            "Entrada_Display",
            "Salida_Display",
            "Razonamiento_Display",
            "Total_Display",
            "Reintentos",
            "Costo_Texto",
        ]
    ].rename(
        columns={
            "Fecha_Hora": "Fecha y Hora (ART)",
            "Integrante": "Integrante",
            "Modelo": "Modelo Gemini",
            "Estado_Display": "Estado",
            "Entrada_Display": "Tokens Entrada",
            "Salida_Display": "Tokens Salida",
            "Razonamiento_Display": "Tokens Razonamiento",
            "Total_Display": "Tokens Totales",
            "Reintentos": "Reintentos",
            "Costo_Texto": "Costo Estimado (USD)",
        }
    )

    st.dataframe(
        df_mostrar,
        use_container_width=True,
        hide_index=True,
    )

    # 9. Botón de exportación a CSV (excluye identificadores privados y secretos)
    csv_bytes = df_mostrar.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Exportar Registro Técnico a CSV",
        data=csv_bytes,
        file_name=f"homelens_consumo_gemini_{date.today().isoformat()}.csv",
        mime="text/csv",
        help="Descarga las operaciones filtradas en formato CSV sin incluir credenciales ni datos personales.",
    )
