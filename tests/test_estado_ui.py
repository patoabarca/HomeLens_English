"""Pruebas unitarias para gestión de estado de sesión, limpieza centralizada y vistas UI."""

from __future__ import annotations
import unittest
from datetime import datetime, timezone
from uuid import uuid4
import streamlit as st

from homelens.modelos import (
    ContextoUsuario,
    Exploracion,
    ObjetoEducativo,
    RecuadroNormalizado,
    EstadoAnalisis,
    ImagenPreparada,
)
from homelens.ui.estado import (
    inicializar_estado_sesion,
    limpiar_datos_exploracion,
    invalidar_preparacion_anterior,
    registrar_nueva_imagen,
    descartar_imagen_actual,
)
from homelens.ui.exploracion import mostrar_exploracion


class TestEstadoUI(unittest.TestCase):

    def setUp(self):
        # Limpiar diccionario de sesión para cada prueba
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        inicializar_estado_sesion()

    def test_inicializar_estado_sesion(self):
        """Comprueba que todas las claves requeridas se inicialicen correctamente."""
        self.assertIn("usuario", st.session_state)
        self.assertIn("imagen_preparada", st.session_state)
        self.assertIn("exploracion_actual", st.session_state)
        self.assertIn("objeto_seleccionado_id", st.session_state)
        self.assertIn("error_analisis", st.session_state)
        self.assertIn("imagen_asociada_id", st.session_state)
        self.assertIsNone(st.session_state.objeto_seleccionado_id)
        self.assertIsNone(st.session_state.exploracion_actual)

    def test_limpiar_datos_exploracion_centralizada(self):
        """Comprueba que la función centralizada de limpieza restablezca todos los datos de sesión."""
        # Configurar un estado ficticio completo
        prep = ImagenPreparada(contenido=b"dummy", mime_type="image/jpeg", ancho=640, alto=480)
        exp_id = uuid4()
        obj_id = uuid4()
        obj = ObjetoEducativo(
            objeto_id=obj_id,
            exploracion_id=exp_id,
            nombre_en="Clock",
            nombre_es="Reloj",
            recuadro=RecuadroNormalizado(ymin=100, xmin=100, ymax=400, xmax=400),
            frase_en="The clock shows the time.",
            frase_es="El reloj muestra la hora.",
        )
        exp = Exploracion(
            exploracion_id=exp_id,
            user_id=uuid4(),
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[obj],
        )

        st.session_state.imagen_cargada_bytes = b"dummy"
        st.session_state.imagen_preparada = prep
        st.session_state.exploracion_actual = exp
        st.session_state.objeto_seleccionado_id = obj_id
        st.session_state.scroll_hacia_foto = True
        st.session_state.error_analisis = "Error previo"
        st.session_state.imagen_asociada_id = hash(b"dummy")
        st.session_state.operacion_en_curso = True

        # Ejecutar función centralizada
        limpiar_datos_exploracion()

        # Comprobar que todos los datos temporales fueron eliminados
        self.assertIsNone(st.session_state.imagen_cargada_bytes)
        self.assertIsNone(st.session_state.imagen_preparada)
        self.assertIsNone(st.session_state.exploracion_actual)
        self.assertIsNone(st.session_state.objeto_seleccionado_id)
        self.assertFalse(st.session_state.scroll_hacia_foto)
        self.assertIsNone(st.session_state.error_analisis)
        self.assertIsNone(st.session_state.imagen_asociada_id)
        self.assertFalse(st.session_state.operacion_en_curso)

    def test_descartar_imagen_actual_incrementa_versiones_widgets(self):
        """Comprueba que descartar la imagen reinicie los componentes de carga."""
        v_uploader_inicial = st.session_state.uploader_version
        v_camara_inicial = st.session_state.camera_version

        descartar_imagen_actual()

        self.assertEqual(st.session_state.uploader_version, v_uploader_inicial + 1)
        self.assertEqual(st.session_state.camera_version, v_camara_inicial + 1)
        self.assertIsNone(st.session_state.imagen_preparada)

    def test_registrar_nueva_imagen_invalida_exploracion_anterior(self):
        """Comprueba que al cargar una nueva imagen se invalide la exploración previa."""
        st.session_state.imagen_cargada_bytes = b"foto_1"
        st.session_state.exploracion_actual = "exploracion_antigua"
        st.session_state.objeto_seleccionado_id = uuid4()

        # Registrar misma imagen: no debe invalidar
        registrar_nueva_imagen(b"foto_1", "archivo")
        self.assertEqual(st.session_state.exploracion_actual, "exploracion_antigua")

        # Registrar imagen diferente: debe invalidar exploración y selección
        registrar_nueva_imagen(b"foto_2_nueva", "archivo")
        self.assertEqual(st.session_state.imagen_cargada_bytes, b"foto_2_nueva")
        self.assertIsNone(st.session_state.exploracion_actual)
        self.assertIsNone(st.session_state.objeto_seleccionado_id)

    def test_mostrar_exploracion_sin_fotografia_no_falla(self):
        """Comprueba que mostrar una exploración cuya imagen ya no está en memoria no falle."""
        exp_id = uuid4()
        obj = ObjetoEducativo(
            objeto_id=uuid4(),
            exploracion_id=exp_id,
            nombre_en="Mug",
            nombre_es="Taza",
            recuadro=RecuadroNormalizado(ymin=100, xmin=100, ymax=400, xmax=400),
            frase_en="This is a mug.",
            frase_es="Esta es una taza.",
        )
        exp = Exploracion(
            exploracion_id=exp_id,
            user_id=uuid4(),
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[obj],
        )

        # Llamar a mostrar_exploracion con imagen=None
        try:
            mostrar_exploracion(exploracion=exp, imagen=None)
        except Exception as e:
            self.fail(f"mostrar_exploracion falló al no haber imagen disponible: {e}")

    def test_mostrar_exploracion_estados_no_utilizables(self):
        """Comprueba el manejo controlado de SIN_OBJETOS_CLAROS y REPETIR_CAPTURA."""
        exp_sin_objetos = Exploracion(
            exploracion_id=uuid4(),
            user_id=uuid4(),
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.SIN_OBJETOS_CLAROS,
            objetos=[],
        )
        exp_repetir = Exploracion(
            exploracion_id=uuid4(),
            user_id=uuid4(),
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.REPETIR_CAPTURA,
            objetos=[],
        )

        try:
            mostrar_exploracion(exploracion=exp_sin_objetos, imagen=None)
            mostrar_exploracion(exploracion=exp_repetir, imagen=None)
        except Exception as e:
            self.fail(f"mostrar_exploracion falló en estados pedagógicos no utilizables: {e}")

    def test_regresion_interaccion_botones_tarjeta_y_selector_con_apptest(self):
        """Prueba de regresión interactiva con AppTest: pulsa botones de tarjetas y cambia el selector."""
        from streamlit.testing.v1 import AppTest

        def _app_simulada():
            import io
            from PIL import Image
            from uuid import UUID
            from datetime import datetime, timezone
            import streamlit as st
            from homelens.modelos import Exploracion, ObjetoEducativo, RecuadroNormalizado, EstadoAnalisis, ImagenPreparada
            from homelens.ui.exploracion import mostrar_exploracion
            from homelens.ui.estado import inicializar_estado_sesion

            inicializar_estado_sesion()

            img = Image.new("RGB", (400, 400), (200, 200, 200))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            prep = ImagenPreparada(buf.getvalue(), "image/jpeg", 400, 400)

            id1 = UUID("00000000-0000-0000-0000-000000000001")
            id2 = UUID("00000000-0000-0000-0000-000000000002")
            obj1 = ObjetoEducativo(id1, UUID("00000000-0000-0000-0000-000000000099"), "Chair", "Silla", RecuadroNormalizado(100, 100, 400, 400), "A chair", "Una silla")
            obj2 = ObjetoEducativo(id2, UUID("00000000-0000-0000-0000-000000000099"), "Table", "Mesa", RecuadroNormalizado(500, 500, 800, 800), "A table", "Una mesa")
            exp = Exploracion(UUID("00000000-0000-0000-0000-000000000099"), UUID("00000000-0000-0000-0000-000000000088"), datetime.now(timezone.utc), EstadoAnalisis.UTILIZABLE, [obj1, obj2])

            mostrar_exploracion(exp, prep)

        at = AppTest.from_function(_app_simulada)
        at.run()
        self.assertEqual(len(at.exception), 0, "Fallo en renderizado inicial")

        # 1. Pulsar botón 'Enfocar #1' desde la tarjeta 1
        btn1 = next(b for b in at.button if "00000000-0000-0000-0000-000000000001" in b.key)
        btn1.click().run()
        self.assertEqual(len(at.exception), 0, "Excepción al pulsar Enfocar #1")
        self.assertEqual(str(at.session_state.objeto_seleccionado_id), "00000000-0000-0000-0000-000000000001")

        # 2. Pulsar botón 'Enfocar #2' desde la tarjeta 2
        btn2 = next(b for b in at.button if "00000000-0000-0000-0000-000000000002" in b.key)
        btn2.click().run()
        self.assertEqual(len(at.exception), 0, "Excepción al pulsar Enfocar #2")
        self.assertEqual(str(at.session_state.objeto_seleccionado_id), "00000000-0000-0000-0000-000000000002")

        # 3. Cambiar opción desde el selector superior
        widget = None
        if at.segmented_control:
            widget = at.segmented_control[0]
        elif at.pills:
            widget = at.pills[0]
        elif at.radio:
            widget = at.radio[0]

        self.assertIsNotNone(widget, "No se encontró widget selector")
        opc_1 = next(o for o in widget.options if "#1" in o)
        widget.select(opc_1).run()
        self.assertEqual(len(at.exception), 0, "Excepción al seleccionar desde widget superior")
        self.assertEqual(str(at.session_state.objeto_seleccionado_id), "00000000-0000-0000-0000-000000000001")

        # 4. Pulsar 'Ver todos' desde la tarjeta
        btn_unfocus = next(b for b in at.button if "btn_unfocus" in b.key)
        btn_unfocus.click().run()
        self.assertEqual(len(at.exception), 0, "Excepción al pulsar Ver todos")
        self.assertIsNone(at.session_state.objeto_seleccionado_id)


if __name__ == "__main__":
    unittest.main()
