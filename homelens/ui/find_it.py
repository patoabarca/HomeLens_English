"""Componente de interfaz para el juego interactivo Find It (Parte 12).

Permite seleccionar un desafío de vocabulario, leer la consigna, subir o
capturar una fotografía, verificarla con Gemini y volver a intentar.
Deja el IntentoPractica resultante disponible en sesión para la Parte 10.
"""

from __future__ import annotations
from typing import Callable, Optional
from uuid import UUID, uuid4
import streamlit as st

from homelens.analisis import verificar_find_it
from homelens.config import Configuracion
from homelens.errores import Resultado
from homelens.exploracion import dibujar_recuadros
from homelens.imagenes import preparar_imagen
from homelens.modelos import (
    ContextoUsuario,
    DesafioFindIt,
    EstadoFindIt,
    ImagenPreparada,
    ObjetoEducativo,
    VerificacionFindIt,
)
from homelens.practicas import (
    construir_intento_find_it,
    obtener_desafios_find_it_disponibles,
)
from homelens.ui.estado import (
    inicializar_estado_sesion,
    limpiar_resultado_find_it,
)


def _reiniciar_intento_find_it() -> None:
    """Limpia la fotografía y el resultado actual conservando el desafío elegido."""
    st.session_state.find_it_imagen_bytes = None
    st.session_state.find_it_imagen_preparada = None
    limpiar_resultado_find_it()
    st.session_state.find_it_uploader_version = st.session_state.get("find_it_uploader_version", 0) + 1
    st.session_state.find_it_camera_version = st.session_state.get("find_it_camera_version", 0) + 1


def renderizar_pantalla_find_it(
    config: Configuracion,
    verificar_fn: Optional[
        Callable[[ContextoUsuario, ImagenPreparada, DesafioFindIt, UUID], Resultado[VerificacionFindIt]]
    ] = None,
) -> None:
    """Renderiza la pantalla de Desafíos Find It conectada a verificar_find_it."""
    inicializar_estado_sesion()

    st.header("🎯 Desafíos Find It")
    st.caption("Encuentra objetos reales de tu entorno y verifica tu hallazgo con inteligencia artificial.")

    usuario: Optional[ContextoUsuario] = st.session_state.get("usuario")
    if usuario is None:
        st.warning("🔒 Inicia sesión para participar en los desafíos Find It.")
        return

    desafios = obtener_desafios_find_it_disponibles(
        usuario=usuario,
        exploracion_actual=st.session_state.get("exploracion_actual"),
    )
    if not desafios:
        st.info("No hay desafíos disponibles en este momento.")
        return

    # 1. Selector de desafío (al cambiar de desafío, limpia el resultado anterior)
    mapa_por_etiqueta = {f"{d.nombre_en} ({d.nombre_es})": d for d in desafios}
    etiquetas_desafios = list(mapa_por_etiqueta.keys())
    desafio_id_previo = st.session_state.get("find_it_desafio_id")
    indice_inicial = 0
    if desafio_id_previo is not None:
        for idx, d in enumerate(desafios):
            if str(d.desafio_id) == str(desafio_id_previo):
                indice_inicial = idx
                break

    etiqueta_seleccionada: str = st.selectbox(
        "Elige un desafío:",
        options=etiquetas_desafios,
        index=indice_inicial,
        key="find_it_selector_desafio",
    )
    desafio_seleccionado = mapa_por_etiqueta[etiqueta_seleccionada]

    if str(desafio_seleccionado.desafio_id) != str(desafio_id_previo):
        st.session_state.find_it_desafio_id = str(desafio_seleccionado.desafio_id)
        limpiar_resultado_find_it()

    # 2. Consigna del desafío
    st.markdown(
        f"""
        <div style='background-color: rgba(2, 132, 199, 0.08); border-left: 4px solid #0284C7; padding: 14px 18px; border-radius: 8px; margin: 10px 0 16px 0;'>
            <div style='font-size: 0.85em; font-weight: 600; color: #0369A1; text-transform: uppercase;'>Consigna del desafío</div>
            <div style='font-size: 1.25em; font-weight: 700; margin-top: 4px;'>
                Find: <span style='color: #0284C7;'>{desafio_seleccionado.nombre_en}</span>
                <span style='font-size: 0.85em; font-weight: 500; color: #475569;'>({desafio_seleccionado.nombre_es})</span>
            </div>
            <div style='font-size: 0.95em; margin-top: 6px;'>
                Busca este objeto a tu alrededor, toma o sube una fotografía clara y presiona <strong>Verificar Desafío</strong>.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Carga o captura de fotografía
    origen_sel = st.radio(
        "Método para enviar tu fotografía:",
        options=["Subir archivo (JPEG / PNG)", "Usar cámara web / móvil"],
        index=0 if st.session_state.get("find_it_origen_imagen", "archivo") == "archivo" else 1,
        horizontal=True,
        key="find_it_radio_origen",
    )
    nuevo_origen = "archivo" if "archivo" in origen_sel.lower() else "camara"
    st.session_state.find_it_origen_imagen = nuevo_origen

    bytes_capturados: Optional[bytes] = None
    uploader_key = f"find_it_uploader_{st.session_state.get('find_it_uploader_version', 0)}"
    camera_key = f"find_it_camera_{st.session_state.get('find_it_camera_version', 0)}"

    if nuevo_origen == "archivo":
        archivo = st.file_uploader(
            "Sube una fotografía del objeto buscado:",
            type=["jpg", "jpeg", "png"],
            key=uploader_key,
        )
        if archivo is not None:
            bytes_capturados = archivo.getvalue()
    else:
        foto = st.camera_input(
            "Toma una fotografía del objeto buscado:",
            key=camera_key,
        )
        if foto is not None:
            bytes_capturados = foto.getvalue()

    # Al cambiar de foto, limpiar resultado anterior y preparar la nueva imagen
    if bytes_capturados is not None and bytes_capturados != st.session_state.get("find_it_imagen_bytes"):
        limpiar_resultado_find_it()
        st.session_state.find_it_imagen_bytes = bytes_capturados
        res_prep = preparar_imagen(
            contenido=bytes_capturados,
            max_bytes=config.max_image_size_bytes,
            max_dimension_px=1280,
        )
        if res_prep.ok and res_prep.valor is not None:
            st.session_state.find_it_imagen_preparada = res_prep.valor
            st.session_state.find_it_error = None
        else:
            st.session_state.find_it_imagen_preparada = None
            st.session_state.find_it_error = (
                res_prep.error.mensaje_usuario if res_prep.error else "No se pudo preparar la imagen."
            )

    imagen_prep: Optional[ImagenPreparada] = st.session_state.get("find_it_imagen_preparada")

    # 4. Vista previa y botón de verificación
    if imagen_prep is not None:
        visor_foto = st.empty()

        verificador = verificar_fn or verificar_find_it
        puede_verificar = bool(config.tiene_gemini or verificar_fn is not None)

        if not puede_verificar:
            st.warning("⚠️ El servicio Gemini no está configurado (`GEMINI_API_KEY`).")

        if st.button(
            "🔍 Verificar Desafío",
            type="primary",
            disabled=not puede_verificar,
            use_container_width=True,
            key="btn_verificar_find_it",
        ):
            with st.spinner("Verificando fotografía con Gemini..."):
                res_verif = verificador(usuario, imagen_prep, desafio_seleccionado, uuid4())

            if res_verif.ok and res_verif.valor is not None:
                st.session_state.find_it_verificacion = res_verif.valor
                st.session_state.find_it_ultimo_desafio = desafio_seleccionado
                st.session_state.find_it_ultimo_intento = construir_intento_find_it(
                    usuario=usuario,
                    desafio=desafio_seleccionado,
                    verificacion=res_verif.valor,
                )
                st.session_state.find_it_error = None
            else:
                st.session_state.find_it_verificacion = None
                st.session_state.find_it_ultimo_intento = None
                st.session_state.find_it_error = (
                    res_verif.error.mensaje_usuario
                    if res_verif.error
                    else "No se pudo completar la verificación con Gemini."
                )

        # Renderizar la foto (con recuadro si fue encontrado) después de procesar el botón
        verificacion_actual: Optional[VerificacionFindIt] = st.session_state.get("find_it_verificacion")
        imagen_a_mostrar = imagen_prep.contenido
        if (
            verificacion_actual is not None
            and verificacion_actual.estado == EstadoFindIt.ENCONTRADO
            and verificacion_actual.recuadro_encontrado is not None
        ):
            obj_temp = ObjetoEducativo(
                objeto_id=desafio_seleccionado.objeto_origen_id,
                exploracion_id=desafio_seleccionado.desafio_id,
                nombre_en=desafio_seleccionado.nombre_en,
                nombre_es=desafio_seleccionado.nombre_es,
                recuadro=verificacion_actual.recuadro_encontrado,
                frase_en="",
                frase_es="",
            )
            imagen_a_mostrar = dibujar_recuadros(imagen_prep, [obj_temp])

        visor_foto.image(
            imagen_a_mostrar,
            caption=f"Fotografía para: {desafio_seleccionado.nombre_en}",
            width="content",
        )

    # 5. Presentación del resultado de los 3 estados y botón Volver a intentar
    verificacion_actual = st.session_state.get("find_it_verificacion")
    error_actual = st.session_state.get("find_it_error")

    if error_actual:
        st.error(f"❌ {error_actual}")

    if verificacion_actual is not None:
        if verificacion_actual.estado == EstadoFindIt.ENCONTRADO:
            st.success(f"🎉 **¡Encontrado!** {verificacion_actual.mensaje}")
        elif verificacion_actual.estado == EstadoFindIt.NO_ENCONTRADO:
            st.warning(f"🔎 **No encontrado:** {verificacion_actual.mensaje}")
        else:
            st.info(f"📷 **No se pudo determinar:** {verificacion_actual.mensaje}")

    if (
        verificacion_actual is not None
        or error_actual is not None
        or st.session_state.get("find_it_imagen_bytes") is not None
    ):
        if st.button(
            "🔄 Volver a intentar",
            use_container_width=True,
            key="btn_reintentar_find_it",
        ):
            _reiniciar_intento_find_it()
            st.rerun()
