"""Suite de pruebas unitarias para el Módulo M3 (Análisis con Gemini).

Pruebas 100% aisladas y simuladas (Mocks) que no requieren claves reales ni realizan
llamadas de red externas.
"""

from __future__ import annotations
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime, timezone

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
    """Pruebas unitarias de validación y análisis M3."""

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

    def test_exploracion_valida_con_un_objeto(self) -> None:
        """Verifica el análisis exitoso con un solo objeto educativo."""
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

    def test_exploracion_valida_con_multiples_objetos(self) -> None:
        """Verifica el análisis exitoso con 3 objetos y preguntas vinculadas."""
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
                )
            ],
        )

        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertTrue(resultado.ok)
        exploracion = resultado.valor
        self.assertEqual(len(exploracion.objetos), 3)
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

    def test_rechazo_exceso_de_objetos(self) -> None:
        """Rechaza respuestas con más de 5 objetos (invariante pedagógico)."""
        objetos_excesivos = [
            ObjetoIA(
                id_local=f"obj_{i}",
                nombre_en=f"item_{i}",
                nombre_es=f"cosa_{i}",
                recuadro=RecuadroIA(ymin=i * 10, xmin=0, ymax=i * 10 + 50, xmax=100),
                frase_en=f"Sentence {i}",
                frase_es=f"Frase {i}",
            )
            for i in range(6)  # 6 objetos
        ]
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=objetos_excesivos,
            actividades=[],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("límite máximo de 5", resultado.error.mensaje_usuario)

    def test_rechazo_coordenadas_fuera_de_rango(self) -> None:
        """Rechaza coordenadas que exceden el rango [0, 1000] en el esquema de IA."""
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            RecuadroIA(ymin=0, xmin=0, ymax=1200, xmax=500)  # ymax > 1000

    def test_rechazo_coordenadas_invertidas_ymin_mayor_igual_ymax(self) -> None:
        """Rechaza recuadros donde ymin >= ymax o xmin >= xmax."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="table",
                    nombre_es="mesa",
                    recuadro=RecuadroIA(ymin=500, xmin=100, ymax=200, xmax=400),  # ymin > ymax
                    frase_en="A dining table.",
                    frase_es="Una mesa de comedor.",
                )
            ],
            actividades=[],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)
        self.assertIn("inválidas", resultado.error.mensaje_usuario)

    def test_rechazo_objeto_con_campos_vacios(self) -> None:
        """Rechaza objetos a los que les faltan nombres o frases requeridas."""
        respuesta_ia = RespuestaExploracionIA(
            estado="UTILIZABLE",
            objetos=[
                ObjetoIA(
                    id_local="obj_1",
                    nombre_en="",  # Vacío
                    nombre_es="silla",
                    recuadro=RecuadroIA(ymin=10, xmin=10, ymax=100, xmax=100),
                    frase_en="A chair.",
                    frase_es="Una silla.",
                )
            ],
            actividades=[],
        )
        adaptador = self._crear_adaptador_mock(Resultado.exito(respuesta_ia))
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_RESPUESTA_INVALIDA)

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

    def test_rechazo_referencia_a_objeto_no_existente(self) -> None:
        """Rechaza actividades que referencian objetos que no fueron detectados."""
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
                    objetos_relacionados=["obj_fantasma_999"],  # Inexistente
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

    def test_manejo_error_cuota_alcanzada(self) -> None:
        """Verifica la propagación controlada del error de límite de cuota (429)."""
        adaptador = self._crear_adaptador_mock(
            Resultado.fallo(
                codigo=CODIGO_LIMITE_ALCANZADO,
                mensaje_usuario="Se ha alcanzado la cuota de peticiones a Gemini.",
                reintentable=False,
                operacion_id=self.operacion_id,
            )
        )
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_LIMITE_ALCANZADO)

    def test_manejo_error_tiempo_agotado(self) -> None:
        """Verifica la propagación de timeout."""
        adaptador = self._crear_adaptador_mock(
            Resultado.fallo(
                codigo=CODIGO_TIEMPO_AGOTADO,
                mensaje_usuario="Tiempo de espera agotado al consultar Gemini.",
                reintentable=True,
                operacion_id=self.operacion_id,
            )
        )
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_TIEMPO_AGOTADO)
        self.assertTrue(resultado.error.reintentable)

    def test_manejo_error_servicio_no_disponible(self) -> None:
        """Verifica la propagación de fallos generales del proveedor."""
        adaptador = self._crear_adaptador_mock(
            Resultado.fallo(
                codigo=CODIGO_SERVICIO_NO_DISPONIBLE,
                mensaje_usuario="El servicio de análisis con Gemini no está disponible.",
                reintentable=True,
                operacion_id=self.operacion_id,
            )
        )
        resultado = analizar_exploracion(self.usuario, self.imagen_prueba, self.operacion_id, adaptador=adaptador)

        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.codigo, CODIGO_SERVICIO_NO_DISPONIBLE)

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
        # Comprobar que el objeto público no contiene el atributo de opción correcta
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
