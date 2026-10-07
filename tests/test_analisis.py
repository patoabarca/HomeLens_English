"""Suite de pruebas unitarias para el Módulo M3 (Análisis con Gemini) usando google-genai.

Pruebas 100% aisladas y simuladas (Mocks) que no requieren claves reales ni realizan
llamadas de red externas.
"""

from __future__ import annotations
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from google.genai import types, errors

from homelens.analisis import analizar_exploracion, obtener_actividades_publicas
from homelens.errores import (
    Resultado,
    CODIGO_RESPUESTA_INVALIDA,
    CODIGO_SERVICIO_NO_DISPONIBLE,
    CODIGO_LIMITE_ALCANZADO,
    CODIGO_TIEMPO_AGOTADO,
    CODIGO_ACCESO_DENEGADO,
    CODIGO_IMAGEN_INVALIDA,
)
from homelens.esquemas_ia import (
    RespuestaExploracionIA,
    ObjetoIA,
    RecuadroIA,
    ActividadIA,
    OpcionIA,
)
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import (
    ContextoUsuario,
    ImagenPreparada,
    EstadoAnalisis,
)


class TestAnalisisGemini(unittest.TestCase):
    """Pruebas unitarias de validación, esquema y análisis M3 con google-genai."""

    def setUp(self) -> None:
        self.usuario = ContextoUsuario(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            sesion_id="sesion-test-123",
        )
        self.imagen_prueba = ImagenPreparada(
            contenido=b"\xff\xd8\xff\xe0" + b"\x00" * 50,
            mime_type="image/jpeg",
            ancho=640,
            alto=480,
        )
        self.operacion_id = uuid4()

    def _crear_adaptador_mock(self, resultado_retornado: Resultado[RespuestaExploracionIA]) -> AdaptadorGemini:
        """Crea un AdaptadorGemini con el método analizar_imagen_exploracion mockeado."""
        adaptador = AdaptadorGemini(api_key="clave-ficticia-de-prueba")
        adaptador.analizar_imagen_exploracion = MagicMock(return_value=resultado_retornado)  # type: ignore
        return adaptador

    # =====================================================================
    # 1. Pruebas de compatibilidad de esquemas con google-genai
    # =====================================================================

    def test_construccion_real_del_esquema_con_sdk(self) -> None:
        """Verifica la serialización de RespuestaExploracionIA en GenerateContentConfig sin red."""
        config_gen = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RespuestaExploracionIA,
            system_instruction="Instrucciones educativas",
        )
        self.assertEqual(config_gen.response_mime_type, "application/json")
        self.assertEqual(config_gen.response_schema, RespuestaExploracionIA)

    # =====================================================================
    # 2. Pruebas de casos exitosos
    # =====================================================================

    def test_exploracion_valida_con_un_objeto_y_actividad(self) -> None:
        """Verifica el análisis exitoso con 1 objeto educativo y 1 actividad."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="mug",
                    nombre_es="taza",
                    recuadro=RecuadroIA(ymin=100, xmin=150, ymax=400, xmax=450),
                    frase_en="This is a ceramic mug.",
                    frase_es="Esta es una taza de cerámica.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="What is on the table?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A mug"),
                        OpcionIA(opcion_id="B", texto="A chair"),
                        OpcionIA(opcion_id="C", texto="A laptop"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="The image shows a ceramic mug on the table.",
                )
            ],
        )

        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertTrue(resultado.ok)
        self.assertIsNotNone(resultado.valor)
        exploracion = resultado.valor
        self.assertEqual(exploracion.estado, EstadoAnalisis.UTILIZABLE)
        self.assertEqual(len(exploracion.objetos), 1)
        self.assertEqual(exploracion.objetos[0].nombre_en, "mug")
        self.assertEqual(exploracion.objetos[0].nombre_es, "taza")
        self.assertEqual(exploracion.objetos[0].recuadro.ymin, 100)
        self.assertEqual(len(exploracion.actividades), 1)
        self.assertEqual(exploracion.actividades[0].opcion_correcta_id, "A")
        self.assertEqual(exploracion.user_id, self.usuario.user_id)

    def test_exploracion_valida_con_multiples_objetos_y_dos_actividades(self) -> None:
        """Verifica el análisis exitoso con 3 objetos y 2 actividades."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="book",
                    nombre_es="libro",
                    recuadro=RecuadroIA(ymin=50, xmin=50, ymax=300, xmax=250),
                    frase_en="I like reading this book.",
                    frase_es="Me gusta leer este libro.",
                ),
                ObjetoIA(
                    id_local="obj_2",
                    nombre_en="lamp",
                    nombre_es="lámpara",
                    recuadro=RecuadroIA(ymin=10, xmin=400, ymax=500, xmax=600),
                    frase_en="The lamp is bright.",
                    frase_es="La lámpara es brillante.",
                ),
                ObjetoIA(
                    id_local="obj_3",
                    nombre_en="clock",
                    nombre_es="reloj",
                    recuadro=RecuadroIA(ymin=20, xmin=700, ymax=200, xmax=850),
                    frase_en="Look at the wall clock.",
                    frase_es="Mira el reloj de pared.",
                ),
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="What do you read?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A lamp"),
                        OpcionIA(opcion_id="B", texto="A book"),
                        OpcionIA(opcion_id="C", texto="A clock"),
                    ],
                    opcion_correcta_id="B",
                    explicacion="'Book' means libro.",
                ),
                ActividadIA(
                    id_local="act_2",
                    objetos_relacionados=["obj_2", "obj_3"],
                    pregunta="Which object gives light?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="The lamp"),
                        OpcionIA(opcion_id="B", texto="The clock"),
                        OpcionIA(opcion_id="C", texto="The book"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="The lamp illuminates the room.",
                ),
            ],
        )

        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertTrue(resultado.ok)
        exploracion = resultado.valor
        self.assertEqual(len(exploracion.objetos), 3)
        self.assertEqual(len(exploracion.actividades), 2)
        self.assertEqual([o.nombre_en for o in exploracion.objetos], ["book", "lamp", "clock"])

    def test_resultado_valido_sin_objetos_claros(self) -> None:
        """Verifica la respuesta cuando la imagen no contiene objetos reconocibles."""
        respuesta_ia = RespuestaExploracionIA(
            estado="SIN_OBJETOS_CLAROS",
            objetos=[],
            actividades=[],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertTrue(resultado.ok)
        exploracion = resultado.valor
        self.assertEqual(exploracion.estado, EstadoAnalisis.SIN_OBJETOS_CLAROS)
        self.assertEqual(len(exploracion.objetos), 0)
        self.assertEqual(len(exploracion.actividades), 0)

    def test_resultado_valido_repetir_captura(self) -> None:
        """Verifica la respuesta cuando el modelo solicita repetir la captura (imagen borrosa/oscura)."""
        respuesta_ia = RespuestaExploracionIA(
            estado="REPETIR_CAPTURA",
            objetos=[],
            actividades=[],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertTrue(resultado.ok)
        exploracion = resultado.valor
        self.assertEqual(exploracion.estado, EstadoAnalisis.REPETIR_CAPTURA)
        self.assertEqual(len(exploracion.objetos), 0)
        self.assertEqual(len(exploracion.actividades), 0)

    # =====================================================================
    # 3. Validación de Estados e Inconsistencias
    # =====================================================================

    def test_rechazo_estado_desconocido(self) -> None:
        """Rechaza estados no definidos en el contrato."""
        respuesta_ia = RespuestaExploracionIA(
            estado="ESTADO_INVENTADO_123",
            objetos=[],
            actividades=[],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("no es reconocido", resultado.error.mensaje_usuario)

    def test_rechazo_inconsistencia_sin_objetos_con_contenido(self) -> None:
        """Rechaza estado SIN_OBJETOS_CLAROS si incluye objetos."""
        respuesta_ia = RespuestaExploracionIA(
            estado="SIN_OBJETOS_CLAROS",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="pen",
                    nombre_es="bolígrafo",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A pen.",
                    frase_es="Un bolígrafo.",
                )
            ],
            actividades=[],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("Inconsistencia", resultado.error.mensaje_usuario)

    def test_rechazo_inconsistencia_repetir_captura_con_actividades(self) -> None:
        """Rechaza estado REPETIR_CAPTURA si incluye actividades."""
        respuesta_ia = RespuestaExploracionIA(
            estado="REPETIR_CAPTURA",
            objetos=[],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="Q?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="1"),
                        OpcionIA(opcion_id="B", texto="2"),
                        OpcionIA(opcion_id="C", texto="3"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="E",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("Inconsistencia", resultado.error.mensaje_usuario)

    def test_rechazo_utilizable_sin_actividades(self) -> None:
        """Rechaza estado UTILIZABLE si no devuelve actividades formativas."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="mug",
                    nombre_es="taza",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A mug.",
                    frase_es="Una taza.",
                )
            ],
            actividades=[],  # Sin actividades
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("actividad formativa", resultado.error.mensaje_usuario)

    def test_rechazo_utilizable_exceso_de_actividades(self) -> None:
        """Rechaza estado UTILIZABLE con más de 2 actividades (límite del contrato)."""
        obj = ObjetoIA(
            id_local="obj_1",
            nombre_en="mug",
            nombre_es="taza",
            recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
            frase_en="A mug.",
            frase_es="Una taza.",
        )
        actividades_excesivas = [
            ActividadIA(
                id_local=f"act_{i}",
                objetos_relacionados=["obj_1"],
                pregunta=f"Pregunta {i}?",
                opciones=[
                    OpcionIA(opcion_id="A", texto=f"Op A {i}"),
                    OpcionIA(opcion_id="B", texto=f"Op B {i}"),
                    OpcionIA(opcion_id="C", texto=f"Op C {i}"),
                ],
                opcion_correcta_id="A",
                explicacion=f"Explicacion {i}",
            )
            for i in range(3)  # 3 actividades > 2
        ]
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[obj],
            actividades=actividades_excesivas,
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("superando el máximo de 2", resultado.error.mensaje_usuario)

    # =====================================================================
    # 4. Validación de Objetos e Identificadores Locales
    # =====================================================================

    def test_rechazo_objeto_con_id_local_vacio(self) -> None:
        """Rechaza objetos con id_local vacío o solo espacios."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="   ",
                    nombre_en="chair",
                    nombre_es="silla",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A chair.",
                    frase_es="Una silla.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="Q?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A"),
                        OpcionIA(opcion_id="B", texto="B"),
                        OpcionIA(opcion_id="C", texto="C"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="E",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("identificador local", resultado.error.mensaje_usuario)

    def test_rechazo_objetos_con_id_local_duplicado(self) -> None:
        """Rechaza objetos con identificadores locales repetidos."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="chair",
                    nombre_es="silla",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A chair.",
                    frase_es="Una silla.",
                ),
                ObjetoIA(
                    id_local="obj_1",  # Duplicado
                    nombre_en="table",
                    nombre_es="mesa",
                    recuadro=RecuadroIA(ymin=200, xmin=200, ymax=400, xmax=400),
                    frase_en="A table.",
                    frase_es="Una mesa.",
                ),
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="Q?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A"),
                        OpcionIA(opcion_id="B", texto="B"),
                        OpcionIA(opcion_id="C", texto="C"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="E",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("duplicado", resultado.error.mensaje_usuario)

    def test_rechazo_exceso_de_objetos(self) -> None:
        """Rechaza respuestas con más de 5 objetos."""
        objetos_excesivos = [
            ObjetoIA(
                id_local=f"obj_{i}",
                nombre_en=f"item_{i}",
                nombre_es=f"cosa_{i}",
                recuadro=RecuadroIA(ymin=i * 10, xmin=0, ymax=i * 10 + 50, xmax=100),
                frase_en=f"Sentence {i}",
                frase_es=f"Frase {i}",
            )
            for i in range(6)
        ]
        actividad = ActividadIA(
            id_local="act_1",
            objetos_relacionados=["obj_0"],
            pregunta="Q?",
            opciones=[
                OpcionIA(opcion_id="A", texto="A"),
                OpcionIA(opcion_id="B", texto="B"),
                OpcionIA(opcion_id="C", texto="C"),
            ],
            opcion_correcta_id="A",
            explicacion="E",
        )
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=objetos_excesivos,
            actividades=[actividad],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("máximo permitido de 5", resultado.error.mensaje_usuario)

    # =====================================================================
    # 5. Validación de Coordenadas y Tipos
    # =====================================================================

    def test_rechazo_coordenadas_fuera_de_rango_negativas_o_mayores_1000(self) -> None:
        """Rechaza coordenadas < 0 o > 1000."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="chair",
                    nombre_es="silla",
                    recuadro=RecuadroIA(ymin=0, xmin=0, ymax=1200, xmax=500),
                    frase_en="A wooden chair.",
                    frase_es="Una silla de madera.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="Q?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A"),
                        OpcionIA(opcion_id="B", texto="B"),
                        OpcionIA(opcion_id="C", texto="C"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="E",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("fuera del rango", resultado.error.mensaje_usuario)

    def test_rechazo_coordenadas_invertidas_y_area_nula(self) -> None:
        """Rechaza recuadros con ymin >= ymax o xmin >= xmax (área nula o invertida)."""
        # Caso 1: ymin == ymax (área nula vertical)
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="table",
                    nombre_es="mesa",
                    recuadro=RecuadroIA(ymin=300, xmin=100, ymax=300, xmax=400),
                    frase_en="A table.",
                    frase_es="Una mesa.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="Q?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A"),
                        OpcionIA(opcion_id="B", texto="B"),
                        OpcionIA(opcion_id="C", texto="C"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="E",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("inválidas", resultado.error.mensaje_usuario)

    def test_rechazo_coordenadas_tipo_booleano(self) -> None:
        """Rechaza coordenadas con valor booleano True/False."""
        rec_mock = MagicMock()
        rec_mock.ymin = True  # booleano
        rec_mock.xmin = 0
        rec_mock.ymax = 100
        rec_mock.xmax = 100

        obj_mock = ObjetoIA(
            id_local="obj_1",
            nombre_en="chair",
            nombre_es="silla",
            recuadro=RecuadroIA(ymin=0, xmin=0, ymax=100, xmax=100),
            frase_en="A chair.",
            frase_es="Una silla.",
        )
        obj_mock.recuadro = rec_mock  # type: ignore

        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[obj_mock],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="Q?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A"),
                        OpcionIA(opcion_id="B", texto="B"),
                        OpcionIA(opcion_id="C", texto="C"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="E",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("Tipo inválido", resultado.error.mensaje_usuario)

    # =====================================================================
    # 6. Validación de Actividades y Referencias
    # =====================================================================

    def test_rechazo_actividad_con_id_local_duplicado(self) -> None:
        """Rechaza actividades con id_local duplicado."""
        obj = ObjetoIA(
            id_local="obj_1",
            nombre_en="pen",
            nombre_es="bolígrafo",
            recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
            frase_en="A pen.",
            frase_es="Un bolígrafo.",
        )
        act1 = ActividadIA(
            id_local="act_1",
            objetos_relacionados=["obj_1"],
            pregunta="Q1?",
            opciones=[
                OpcionIA(opcion_id="A", texto="1"),
                OpcionIA(opcion_id="B", texto="2"),
                OpcionIA(opcion_id="C", texto="3"),
            ],
            opcion_correcta_id="A",
            explicacion="E1",
        )
        act2 = ActividadIA(
            id_local="act_1",  # Duplicado
            objetos_relacionados=["obj_1"],
            pregunta="Q2?",
            opciones=[
                OpcionIA(opcion_id="A", texto="4"),
                OpcionIA(opcion_id="B", texto="5"),
                OpcionIA(opcion_id="C", texto="6"),
            ],
            opcion_correcta_id="A",
            explicacion="E2",
        )
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[obj],
            actividades=[act1, act2],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("duplicado", resultado.error.mensaje_usuario)

    def test_rechazo_actividad_sin_referencias_a_objetos(self) -> None:
        """Rechaza actividades sin referencias y no asocia automáticamente al primer objeto."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="pen",
                    nombre_es="bolígrafo",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A pen.",
                    frase_es="Un bolígrafo.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=[],  # Sin referencias
                    pregunta="What is this?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A pen"),
                        OpcionIA(opcion_id="B", texto="A book"),
                        OpcionIA(opcion_id="C", texto="A pencil"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="Explanation",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("no incluye referencias", resultado.error.mensaje_usuario)

    def test_rechazo_actividad_con_referencias_repetidas(self) -> None:
        """Rechaza actividades con referencias a objetos duplicadas dentro de la misma lista."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="pen",
                    nombre_es="bolígrafo",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A pen.",
                    frase_es="Un bolígrafo.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1", "obj_1"],  # Repetido
                    pregunta="What is this?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A pen"),
                        OpcionIA(opcion_id="B", texto="A book"),
                        OpcionIA(opcion_id="C", texto="A pencil"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="Explanation",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("referencias a objetos repetidas", resultado.error.mensaje_usuario)

    def test_rechazo_referencia_a_objeto_no_existente(self) -> None:
        """Rechaza actividades que referencian objetos que no fueron devueltos."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="key",
                    nombre_es="llave",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A metal key.",
                    frase_es="Una llave de metal.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_fantasma_999"],
                    pregunta="What is this?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="Key"),
                        OpcionIA(opcion_id="B", texto="Door"),
                        OpcionIA(opcion_id="C", texto="Window"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="Explanation",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("no reconocido", resultado.error.mensaje_usuario)

    def test_rechazo_actividad_con_opciones_duplicadas(self) -> None:
        """Rechaza actividades con opciones de texto o ID repetido."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="pen",
                    nombre_es="bolígrafo",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A blue pen.",
                    frase_es="Un bolígrafo azul.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="What is this?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A pen"),
                        OpcionIA(opcion_id="B", texto="A pen"),  # Texto repetido
                        OpcionIA(opcion_id="C", texto="A pencil"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="Explanation",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("repetido", resultado.error.mensaje_usuario)

    def test_rechazo_actividad_con_solucion_inexistente(self) -> None:
        """Rechaza actividades donde la opcion_correcta_id no figura entre las opciones."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="cup",
                    nombre_es="taza",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A cup.",
                    frase_es="Una taza.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="What is this?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="Cup"),
                        OpcionIA(opcion_id="B", texto="Fork"),
                        OpcionIA(opcion_id="C", texto="Spoon"),
                    ],
                    opcion_correcta_id="Z",  # Inexistente
                    explicacion="Explanation",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("no pertenece a las opciones", resultado.error.mensaje_usuario)

    # =====================================================================
    # 7. Pruebas del AdaptadorGemini con Cliente SDK Simulado
    # =====================================================================

    def test_adaptador_con_cliente_sdk_simulado_exito(self) -> None:
        """Prueba AdaptadorGemini simulando models.generate_content del SDK."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"estado": "SIN_OBJETOS_CLAROS", "objetos": [], "actividades": []}'
        mock_response.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=20, total_token_count=30)
        mock_client.models.generate_content.return_value = mock_response

        adaptador = AdaptadorGemini(api_key="key-test", cliente=mock_client)
        resultado = adaptador.analizar_imagen_exploracion(
            imagen_bytes=self.imagen_prueba.contenido,
            mime_type=self.imagen_prueba.mime_type,
            instrucciones="instrucciones",
            operacion_id=self.operacion_id,
        )

        self.assertTrue(resultado.ok)
        self.assertEqual(resultado.valor.estado, "SIN_OBJETOS_CLAROS")
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

    def test_adaptador_error_cuota_429(self) -> None:
        """Verifica que el error 429 de cuota mapea a CODIGO_LIMITE_ALCANZADO y no se reintenta."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = errors.APIError(
            code=429,
            response_json={"error": {"message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}},
        )

        adaptador = AdaptadorGemini(api_key="key-test", cliente=mock_client, max_reintentos=2)
        resultado = adaptador.analizar_imagen_exploracion(
            imagen_bytes=self.imagen_prueba.contenido,
            mime_type=self.imagen_prueba.mime_type,
            instrucciones="instrucciones",
            operacion_id=self.operacion_id,
        )

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_LIMITE_ALCANZADO)
        self.assertFalse(resultado.error.reintentable)
        # 429 es permanente para el intento, no debe reintentar
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

    def test_adaptador_error_autenticacion_401(self) -> None:
        """Verifica que el error 401 mapea a CODIGO_ACCESO_DENEGADO y no se reintenta."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = errors.APIError(
            code=401,
            response_json={"error": {"message": "Unauthenticated", "status": "UNAUTHENTICATED"}},
        )

        adaptador = AdaptadorGemini(api_key="key-test", cliente=mock_client, max_reintentos=2)
        resultado = adaptador.analizar_imagen_exploracion(
            imagen_bytes=self.imagen_prueba.contenido,
            mime_type=self.imagen_prueba.mime_type,
            instrucciones="instrucciones",
            operacion_id=self.operacion_id,
        )

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_ACCESO_DENEGADO)
        self.assertFalse(resultado.error.reintentable)
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

    def test_adaptador_error_transitorio_503_reintenta(self) -> None:
        """Verifica que un error 503 del servidor es reintentable."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = errors.APIError(
            code=503,
            response_json={"error": {"message": "Service Unavailable", "status": "UNAVAILABLE"}},
        )

        adaptador = AdaptadorGemini(api_key="key-test", cliente=mock_client, max_reintentos=1)
        resultado = adaptador.analizar_imagen_exploracion(
            imagen_bytes=self.imagen_prueba.contenido,
            mime_type=self.imagen_prueba.mime_type,
            instrucciones="instrucciones",
            operacion_id=self.operacion_id,
        )

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_SERVICIO_NO_DISPONIBLE)
        self.assertTrue(resultado.error.reintentable)
        # 1 intento inicial + 1 reintento = 2 llamadas
        self.assertEqual(mock_client.models.generate_content.call_count, 2)

    def test_adaptador_error_tiempo_agotado(self) -> None:
        """Verifica el mapeo de TimeoutError a CODIGO_TIEMPO_AGOTADO."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = TimeoutError("Deadline exceeded")

        adaptador = AdaptadorGemini(api_key="key-test", cliente=mock_client, max_reintentos=0)
        resultado = adaptador.analizar_imagen_exploracion(
            imagen_bytes=self.imagen_prueba.contenido,
            mime_type=self.imagen_prueba.mime_type,
            instrucciones="instrucciones",
            operacion_id=self.operacion_id,
        )

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_TIEMPO_AGOTADO)
        self.assertTrue(resultado.error.reintentable)

    def test_adaptador_respuesta_bloqueada_o_vacia(self) -> None:
        """Verifica el manejo cuando Gemini devuelve texto vacío o bloqueo de seguridad."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""  # Texto vacío
        mock_response.prompt_feedback = MagicMock(block_reason="SAFETY")
        mock_client.models.generate_content.return_value = mock_response

        adaptador = AdaptadorGemini(api_key="key-test", cliente=mock_client)
        resultado = adaptador.analizar_imagen_exploracion(
            imagen_bytes=self.imagen_prueba.contenido,
            mime_type=self.imagen_prueba.mime_type,
            instrucciones="instrucciones",
            operacion_id=self.operacion_id,
        )

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("filtros de seguridad", resultado.error.mensaje_usuario)

    def test_adaptador_sin_credenciales_falla_amigablemente(self) -> None:
        """El AdaptadorGemini sin API key retorna fallo controlado sin lanzar excepción."""
        adaptador = AdaptadorGemini(api_key=None)
        resultado = adaptador.analizar_imagen_exploracion(
            imagen_bytes=self.imagen_prueba.contenido,
            mime_type=self.imagen_prueba.mime_type,
            instrucciones="test",
            operacion_id=self.operacion_id,
        )
        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_SERVICIO_NO_DISPONIBLE)
        self.assertIn("GEMINI_API_KEY", resultado.error.mensaje_usuario)

    # =====================================================================
    # 8. Seguridad y Proyección Pública
    # =====================================================================

    def test_proyeccion_actividades_publicas_no_expone_solucion(self) -> None:
        """Comprueba que ActividadPublica oculta la solución y explicación antes de confirmar."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="bottle",
                    nombre_es="botella",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A water bottle.",
                    frase_es="Una botella de agua.",
                )
            ],
            actividades=[
                ActividadIA(
                    id_local="act_1",
                    objetos_relacionados=["obj_1"],
                    pregunta="What is in the photo?",
                    opciones=[
                        OpcionIA(opcion_id="A", texto="A bottle"),
                        OpcionIA(opcion_id="B", texto="A plate"),
                        OpcionIA(opcion_id="C", texto="A cup"),
                    ],
                    opcion_correcta_id="A",
                    explicacion="Secret educational explanation",
                )
            ],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)
        self.assertTrue(resultado.ok)

        actividades_publicas = obtener_actividades_publicas(resultado.valor.actividades)
        self.assertEqual(len(actividades_publicas), 1)
        pub = actividades_publicas[0]
        self.assertEqual(pub.pregunta, "What is in the photo?")
        self.assertEqual(len(pub.opciones), 3)
        self.assertFalse(hasattr(pub, "opcion_correcta_id"))
        self.assertFalse(hasattr(pub, "explicacion"))

    def test_rechazo_imagen_nula_o_vacia(self) -> None:
        """Rechaza solicitudes con imagen vacía o sin bytes."""
        imagen_invalida = ImagenPreparada(
            contenido=b"",
            mime_type="image/jpeg",
            ancho=0,
            alto=0,
        )
        resultado = analizar_exploracion(self.usuario, imagen_invalida, self.operacion_id)
        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_IMAGEN_INVALIDA)


if __name__ == "__main__":
    unittest.main()
