"""Pruebas automatizadas para la pantalla «Mi Progreso» (M8 - Parte 14)."""

from __future__ import annotations
import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5, NAMESPACE_DNS
from streamlit.testing.v1 import AppTest

from homelens.ui.progreso import formatear_porcentaje_aciertos


class TestPantallaMiProgresoParte14(unittest.TestCase):
    """Verifica todos los escenarios de la vista Mi Progreso en homelens/ui/progreso.py."""

    def test_formatear_porcentaje_aciertos_diferencia_none_y_cero_real(self) -> None:
        self.assertEqual(formatear_porcentaje_aciertos(None), "Sin intentos evaluables")
        self.assertEqual(formatear_porcentaje_aciertos(0.0), "0 %")
        self.assertEqual(formatear_porcentaje_aciertos(0), "0 %")
        self.assertEqual(formatear_porcentaje_aciertos(50.0), "50 %")
        self.assertEqual(formatear_porcentaje_aciertos(66.67), "66.67 %")
        self.assertEqual(formatear_porcentaje_aciertos(100.0), "100 %")

    def test_cuenta_sin_actividad_muestra_guia_inicio_sin_error(self) -> None:
        codigo = """
from uuid import uuid4
import streamlit as st
from homelens.modelos import ContextoUsuario
from homelens.ui.estado import inicializar_estado_sesion
from homelens.ui.progreso import renderizar_pantalla_progreso

inicializar_estado_sesion()
st.session_state.usuario = ContextoUsuario(
    user_id=uuid4(),
    sesion_id="demo-vacio",
    nombre="Estudiante Nuevo",
    es_demo=True,
)
renderizar_pantalla_progreso()
"""
        at = AppTest.from_string(codigo)
        at.run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.error), 0)

        metricas = {m.label: m.value for m in at.metric}
        self.assertEqual(metricas.get("Palabras exploradas"), "0")
        self.assertEqual(metricas.get("Palabras practicadas"), "0")
        self.assertEqual(metricas.get("Intentos registrados"), "0")

        infos = "\n".join(i.value for i in at.info)
        self.assertIn("Exploración Visual", infos)
        self.assertIn("Find It", infos)

    def test_resultados_ambas_actividades_palabra_base_y_nota_no_resueltos(self) -> None:
        obj_explorada_id = uuid4()
        obj_no_resuelto_id = uuid4()
        obj_keys_base_id = uuid5(NAMESPACE_DNS, "homelens:objeto_base:keys")

        codigo = f"""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import MagicMock
import streamlit as st
from homelens.errores import Resultado
from homelens.modelos import (
    ContextoUsuario,
    IntentoPractica,
    ObjetoEducativo,
    RecuadroNormalizado,
    ResultadoIntento,
    TipoIntento,
)
from homelens.ui.estado import inicializar_estado_sesion
from homelens.ui.progreso import renderizar_pantalla_progreso

inicializar_estado_sesion()
uid = uuid4()
st.session_state.usuario = ContextoUsuario(
    user_id=uid,
    sesion_id="sesion-activa",
    nombre="Patricia",
    es_demo=False,
)

obj_lamp = ObjetoEducativo(
    objeto_id=UUID("{obj_explorada_id}"),
    exploracion_id=uuid4(),
    nombre_en="Lamp",
    nombre_es="Lámpara",
    recuadro=RecuadroNormalizado(100, 100, 400, 400),
    frase_en="The lamp is bright.",
    frase_es="La lámpara es brillante.",
)

intentos = [
    # Cuestionario correcto sobre Lamp (explorada)
    IntentoPractica(
        intento_id=uuid4(),
        user_id=uid,
        tipo=TipoIntento.CUESTIONARIO,
        fecha=datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc),
        actividad_id=uuid4(),
        opcion_elegida_id="A",
        resultado=ResultadoIntento.CORRECTO,
        objeto_ids=[UUID("{obj_explorada_id}")],
    ),
    # Cuestionario incorrecto sobre exploración no guardada (objeto_id no resuelto)
    IntentoPractica(
        intento_id=uuid4(),
        user_id=uid,
        tipo=TipoIntento.CUESTIONARIO,
        fecha=datetime(2026, 11, 27, 15, 5, tzinfo=timezone.utc),
        actividad_id=uuid4(),
        opcion_elegida_id="B",
        resultado=ResultadoIntento.INCORRECTO,
        objeto_ids=[UUID("{obj_no_resuelto_id}")],
    ),
    # Find It encontrado sobre Keys (catálogo base, no explorada en foto)
    IntentoPractica(
        intento_id=uuid4(),
        user_id=uid,
        tipo=TipoIntento.FIND_IT,
        fecha=datetime(2026, 11, 27, 16, 0, tzinfo=timezone.utc),
        desafio_id=uuid4(),
        resultado=ResultadoIntento.CORRECTO,
        objeto_ids=[UUID("{obj_keys_base_id}")],
    ),
    # Find It indeterminable
    IntentoPractica(
        intento_id=uuid4(),
        user_id=uid,
        tipo=TipoIntento.FIND_IT,
        fecha=datetime(2026, 11, 27, 16, 10, tzinfo=timezone.utc),
        desafio_id=uuid4(),
        resultado=ResultadoIntento.INDETERMINABLE,
        objeto_ids=[UUID("{obj_keys_base_id}")],
    ),
]

repo = MagicMock()
repo.listar_vocabulario.return_value = Resultado.exito([obj_lamp])
repo.listar_intentos.return_value = Resultado.exito(intentos)

renderizar_pantalla_progreso(repositorio=repo)
"""
        at = AppTest.from_string(codigo)
        at.run()
        self.assertEqual(len(at.exception), 0)

        metricas = {m.label: m.value for m in at.metric}
        self.assertEqual(metricas.get("Palabras exploradas"), "1")
        self.assertEqual(metricas.get("Palabras practicadas"), "2")
        self.assertEqual(metricas.get("Intentos registrados"), "4")

        self.assertEqual(metricas.get("Respuestas correctas"), "1")
        self.assertEqual(metricas.get("Respuestas incorrectas"), "1")
        self.assertEqual(metricas.get("Porcentaje de aciertos (Cuestionarios)"), "50 %")

        self.assertEqual(metricas.get("Encontrados"), "1")
        self.assertEqual(metricas.get("No encontrados"), "0")
        self.assertEqual(metricas.get("Indeterminables"), "1")
        self.assertEqual(metricas.get("Porcentaje de aciertos (Find It)"), "100 %")

        # Nota sobre objetos no resueltos sin exponer UUIDs internos
        infos = "\n".join(i.value for i in at.info)
        self.assertIn(
            "Algunos intentos cuentan en tus resultados, pero su palabra no está disponible",
            infos,
        )
        markdown_total = "\n".join(m.value for m in at.markdown)
        self.assertIn("Lamp", markdown_total)
        self.assertIn("Lámpara", markdown_total)
        self.assertIn("Keys", markdown_total)
        self.assertIn("Llaves", markdown_total)
        self.assertNotIn(str(obj_explorada_id), markdown_total)
        self.assertNotIn(str(obj_no_resuelto_id), markdown_total)
        self.assertNotIn(str(obj_keys_base_id), markdown_total)

    def test_porcentaje_cero_real_y_find_it_solo_indeterminable(self) -> None:
        obj_chair_base_id = uuid5(NAMESPACE_DNS, "homelens:objeto_base:chair")
        codigo = f"""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import MagicMock
import streamlit as st
from homelens.errores import Resultado
from homelens.modelos import (
    ContextoUsuario,
    IntentoPractica,
    ResultadoIntento,
    TipoIntento,
)
from homelens.ui.estado import inicializar_estado_sesion
from homelens.ui.progreso import renderizar_pantalla_progreso

inicializar_estado_sesion()
uid = uuid4()
st.session_state.usuario = ContextoUsuario(
    user_id=uid,
    sesion_id="sesion-cero-real",
    nombre="Lucas",
    es_demo=False,
)

intentos = [
    # Cuestionario con 0 % real (0 correctas, 1 incorrecta)
    IntentoPractica(
        intento_id=uuid4(),
        user_id=uid,
        tipo=TipoIntento.CUESTIONARIO,
        fecha=datetime(2026, 11, 27, 17, 0, tzinfo=timezone.utc),
        actividad_id=uuid4(),
        opcion_elegida_id="C",
        resultado=ResultadoIntento.INCORRECTO,
        objeto_ids=[UUID("{obj_chair_base_id}")],
    ),
    # Find It únicamente con intento indeterminable (porcentaje -> None -> Sin intentos evaluables)
    IntentoPractica(
        intento_id=uuid4(),
        user_id=uid,
        tipo=TipoIntento.FIND_IT,
        fecha=datetime(2026, 11, 27, 17, 5, tzinfo=timezone.utc),
        desafio_id=uuid4(),
        resultado=ResultadoIntento.INDETERMINABLE,
        objeto_ids=[UUID("{obj_chair_base_id}")],
    ),
]

repo = MagicMock()
repo.listar_vocabulario.return_value = Resultado.exito([])
repo.listar_intentos.return_value = Resultado.exito(intentos)

renderizar_pantalla_progreso(repositorio=repo)
"""
        at = AppTest.from_string(codigo)
        at.run()
        self.assertEqual(len(at.exception), 0)

        metricas = {m.label: m.value for m in at.metric}
        self.assertEqual(metricas.get("Porcentaje de aciertos (Cuestionarios)"), "0 %")
        self.assertEqual(metricas.get("Indeterminables"), "1")
        self.assertEqual(
            metricas.get("Porcentaje de aciertos (Find It)"),
            "Sin intentos evaluables",
        )

    def test_error_de_consulta_muestra_mensaje_y_boton_reintentar(self) -> None:
        codigo = """
from uuid import uuid4
from unittest.mock import MagicMock
import streamlit as st
from homelens.errores import CODIGO_PERSISTENCIA_FALLIDA, Resultado
from homelens.modelos import ContextoUsuario
from homelens.ui.estado import inicializar_estado_sesion
from homelens.ui.progreso import renderizar_pantalla_progreso

inicializar_estado_sesion()
st.session_state.usuario = ContextoUsuario(
    user_id=uuid4(),
    sesion_id="sesion-error",
    nombre="Victoria",
    es_demo=False,
)

repo = MagicMock()
repo.listar_vocabulario.return_value = Resultado.fallo(
    codigo=CODIGO_PERSISTENCIA_FALLIDA,
    mensaje_usuario="No se pudo conectar con la base de datos para leer tu vocabulario.",
    reintentable=True,
)

renderizar_pantalla_progreso(repositorio=repo)
"""
        at = AppTest.from_string(codigo)
        at.run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.error), 1)
        self.assertIn(
            "No se pudo conectar con la base de datos para leer tu vocabulario.",
            at.error[0].value,
        )
        # No debe confundirse con cuenta vacía
        self.assertEqual(len(at.info), 0)
        botones_retry = [b for b in at.button if b.key == "btn_reintentar_progreso"]
        self.assertEqual(len(botones_retry), 1)


if __name__ == "__main__":
    unittest.main()
