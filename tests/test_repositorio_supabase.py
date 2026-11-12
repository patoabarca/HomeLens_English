"""Pruebas unitarias e integración simulada para el Repositorio de Supabase (M7).

Valida el guardado atómico, reconstrucción fiel de modelos, prevención de duplicados,
aislamiento RLS entre usuarios, modo demo aislado y tolerancia a fallos.
"""

import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Any, Dict, List

from homelens.errores import (
    CODIGO_SESION_REQUERIDA,
    CODIGO_ACCESO_DENEGADO,
    CODIGO_PERSISTENCIA_FALLIDA,
    CODIGO_CONFIGURACION_INVALIDA,
)
from homelens.modelos import (
    ContextoUsuario,
    Exploracion,
    ResumenExploracion,
    ObjetoEducativo,
    Actividad,
    Opcion,
    RecuadroNormalizado,
    EstadoAnalisis,
)
from homelens.datos.supabase import RepositorioSupabase


class MockPostgrestResponse:
    """Simula la respuesta devuelta por execute() en postgrest-py."""

    def __init__(self, data: Any = None, count: int = 0):
        self.data = data if data is not None else []
        self.count = count


class MockSupabaseQuery:
    """Simulador de la interfaz fluida de consultas de Supabase / PostgREST."""

    def __init__(self, db: Dict[str, List[Dict[str, Any]]], table_name: str, auth_token: str = ""):
        self.db = db
        self.table_name = table_name
        self.auth_token = auth_token
        self._action = "SELECT"
        self._select_fields = "*"
        self._filters: List[tuple] = []
        self._order_field: str = ""
        self._order_desc: bool = False
        self._limit_val: int = 0
        self._insert_data: Any = None
        self.simular_error_conexion = False
        self.simular_error_duplicado = False

    def select(self, fields: str = "*"):
        self._action = "SELECT"
        self._select_fields = fields
        return self

    def insert(self, data: Any):
        self._action = "INSERT"
        self._insert_data = data
        return self

    def eq(self, column: str, value: Any):
        self._filters.append((column, str(value)))
        return self

    def order(self, column: str, desc: bool = False):
        self._order_field = column
        self._order_desc = desc
        return self

    def limit(self, count: int):
        self._limit_val = count
        return self

    def execute(self) -> MockPostgrestResponse:
        if self.simular_error_conexion:
            raise ConnectionError("No fue posible conectar con el servidor de base de datos.")

        if self.simular_error_duplicado:
            raise Exception("duplicate key value violates unique constraint 23505")

        table = self.db.setdefault(self.table_name, [])

        if self._action == "INSERT":
            row = dict(self._insert_data)
            # Simular constraint UNIQUE sobre la columna 'id'
            for existing in table:
                if existing.get("id") == row.get("id"):
                    raise Exception("duplicate key value violates unique constraint 'exploraciones_pkey' (23505)")
            table.append(row)
            return MockPostgrestResponse(data=[row], count=1)

        if self._action == "SELECT":
            results = []
            for row in table:
                match = True
                for col, val in self._filters:
                    if str(row.get(col)) != str(val):
                        match = False
                        break
                if match:
                    results.append(dict(row))

            if self._order_field:
                results.sort(
                    key=lambda r: r.get(self._order_field, ""),
                    reverse=self._order_desc,
                )

            if self._limit_val > 0:
                results = results[: self._limit_val]

            return MockPostgrestResponse(data=results, count=len(results))

        return MockPostgrestResponse(data=[])


class MockSupabaseClient:
    """Cliente simulado de Supabase con soporte para RLS y cabeceras JWT."""

    def __init__(self):
        self.db: Dict[str, List[Dict[str, Any]]] = {}
        self.current_token: str = ""
        self.fallar_conexion = False

        class PostgrestAuth:
            def __init__(self, parent):
                self.parent = parent

            def auth(self, token: str):
                self.parent.current_token = token

        self.postgrest = PostgrestAuth(self)

    def table(self, table_name: str) -> MockSupabaseQuery:
        query = MockSupabaseQuery(self.db, table_name, auth_token=self.current_token)
        if self.fallar_conexion:
            query.simular_error_conexion = True
        return query


class TestRepositorioSupabase(unittest.TestCase):
    """Batería de pruebas para persistencia, seguridad e historial (M7)."""

    def setUp(self):
        self.user_a_id = UUID("11111111-1111-1111-1111-111111111111")
        self.user_b_id = UUID("22222222-2222-2222-2222-222222222222")

        self.usuario_a = ContextoUsuario(
            user_id=self.user_a_id,
            sesion_id="token_jwt_usuario_a",
            email="alumno.a@gmail.com",
            nombre="Alumno A",
            es_demo=False,
        )

        self.usuario_b = ContextoUsuario(
            user_id=self.user_b_id,
            sesion_id="token_jwt_usuario_b",
            email="alumno.b@gmail.com",
            nombre="Alumno B",
            es_demo=False,
        )

        self.usuario_demo = ContextoUsuario(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            sesion_id="sesion_demo_local",
            email="demo@homelens.edu",
            nombre="Estudiante Demo",
            es_demo=True,
        )

        self.mock_client = MockSupabaseClient()
        self.repo = RepositorioSupabase(
            supabase_url="https://test.supabase.co",
            anon_key="test_anon_key",
            cliente_supabase=self.mock_client,
        )

        # Creación de una exploración educativa de prueba completa
        self.exp_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        self.obj_1_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        self.obj_2_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        self.act_1_id = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

        self.obj_1 = ObjetoEducativo(
            objeto_id=self.obj_1_id,
            exploracion_id=self.exp_id,
            nombre_en="Coffee Mug",
            nombre_es="Taza de café",
            recuadro=RecuadroNormalizado(ymin=100, xmin=150, ymax=450, xmax=500),
            frase_en="This is a ceramic coffee mug on the table.",
            frase_es="Esta es una taza de café de cerámica sobre la mesa.",
        )

        self.obj_2 = ObjetoEducativo(
            objeto_id=self.obj_2_id,
            exploracion_id=self.exp_id,
            nombre_en="Notebook",
            nombre_es="Cuaderno",
            recuadro=RecuadroNormalizado(ymin=500, xmin=200, ymax=800, xmax=600),
            frase_en="I write notes in my notebook every morning.",
            frase_es="Escribo notas en mi cuaderno todas las mañanas.",
        )

        self.act_1 = Actividad(
            actividad_id=self.act_1_id,
            exploracion_id=self.exp_id,
            objeto_ids=[self.obj_1_id],
            pregunta="What do you use to drink coffee?",
            opciones=[
                Opcion(opcion_id="A", texto="A notebook"),
                Opcion(opcion_id="B", texto="A coffee mug"),
                Opcion(opcion_id="C", texto="A lamp"),
            ],
            opcion_correcta_id="B",
            explicacion="A coffee mug is used for hot beverages like coffee.",
        )

        self.exploracion_a = Exploracion(
            exploracion_id=self.exp_id,
            user_id=self.user_a_id,
            creada_en=datetime(2026, 11, 4, 12, 0, 0, tzinfo=timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[self.obj_1, self.obj_2],
            actividades=[self.act_1],
            schema_version=1,
        )

    def test_01_guardado_completo_y_recuperacion(self):
        """Verifica el guardado atómico y la recuperación íntegra de una exploración."""
        # 1. Guardar
        res_guardar = self.repo.guardar_exploracion(self.usuario_a, self.exploracion_a)
        self.assertTrue(res_guardar.ok)
        self.assertEqual(res_guardar.valor, self.exp_id)

        # 2. Recuperar
        res_recup = self.repo.obtener_exploracion(self.usuario_a, self.exp_id)
        self.assertTrue(res_recup.ok)
        exp_recuperada = res_recup.valor

        # Validar consistencia de identidades y metadatos
        self.assertEqual(exp_recuperada.exploracion_id, self.exp_id)
        self.assertEqual(exp_recuperada.user_id, self.user_a_id)
        self.assertEqual(exp_recuperada.estado, EstadoAnalisis.UTILIZABLE)
        self.assertEqual(len(exp_recuperada.objetos), 2)
        self.assertEqual(len(exp_recuperada.actividades), 1)

        # Validar objetos y coordenadas normalizadas
        o1 = exp_recuperada.objetos[0]
        self.assertEqual(o1.objeto_id, self.obj_1_id)
        self.assertEqual(o1.nombre_en, "Coffee Mug")
        self.assertEqual(o1.nombre_es, "Taza de café")
        self.assertEqual(o1.recuadro.ymin, 100)
        self.assertEqual(o1.recuadro.xmax, 500)

        # Validar actividad pedagógica completa
        act = exp_recuperada.actividades[0]
        self.assertEqual(act.actividad_id, self.act_1_id)
        self.assertEqual(act.pregunta, "What do you use to drink coffee?")
        self.assertEqual(len(act.opciones), 3)
        self.assertEqual(act.opcion_correcta_id, "B")
        self.assertEqual(act.explicacion, "A coffee mug is used for hot beverages like coffee.")

    def test_02_ausencia_de_duplicados_por_doble_pulsacion(self):
        """Verifica que intentar guardar dos veces la misma exploración sea rechazado limpiamente."""
        # Primer guardado
        res1 = self.repo.guardar_exploracion(self.usuario_a, self.exploracion_a)
        self.assertTrue(res1.ok)

        # Segundo intento de guardado (simula doble clic)
        res2 = self.repo.guardar_exploracion(self.usuario_a, self.exploracion_a)
        self.assertFalse(res2.ok)
        self.assertEqual(res2.error.codigo, CODIGO_PERSISTENCIA_FALLIDA)
        self.assertIn("ya se encuentra guardada", res2.error.mensaje_usuario.lower())

        # Verificar que solo exista un registro en la tabla
        filas = self.mock_client.db.get("exploraciones", [])
        self.assertEqual(len(filas), 1)

    def test_03_reconstruccion_fiel_de_modelos_de_dominio(self):
        """Comprueba que los tipos de datos devueltos correspondan a las dataclasses del dominio."""
        self.repo.guardar_exploracion(self.usuario_a, self.exploracion_a)
        res = self.repo.obtener_exploracion(self.usuario_a, self.exp_id)
        self.assertTrue(res.ok)
        e = res.valor

        self.assertIsInstance(e, Exploracion)
        self.assertIsInstance(e.objetos[0], ObjetoEducativo)
        self.assertIsInstance(e.objetos[0].recuadro, RecuadroNormalizado)
        self.assertIsInstance(e.actividades[0], Actividad)
        self.assertIsInstance(e.actividades[0].opciones[0], Opcion)

    def test_04_aislamiento_estricto_entre_dos_usuarios(self):
        """Verifica que un usuario B no pueda consultar ni listar exploraciones del usuario A."""
        # Usuario A guarda su exploración
        self.repo.guardar_exploracion(self.usuario_a, self.exploracion_a)

        # Usuario B intenta obtener directamente la exploración de A por su UUID
        res_b = self.repo.obtener_exploracion(self.usuario_b, self.exp_id)
        self.assertFalse(res_b.ok)
        self.assertEqual(res_b.error.codigo, CODIGO_PERSISTENCIA_FALLIDA)

        # Usuario B lista sus exploraciones: debe estar vacío
        res_listado_b = self.repo.listar_exploraciones(self.usuario_b)
        self.assertTrue(res_listado_b.ok)
        self.assertEqual(len(res_listado_b.valor), 0)

        # Usuario A lista sus exploraciones: debe contener su exploración
        res_listado_a = self.repo.listar_exploraciones(self.usuario_a)
        self.assertTrue(res_listado_a.ok)
        self.assertEqual(len(res_listado_a.valor), 1)
        self.assertEqual(res_listado_a.valor[0].exploracion_id, self.exp_id)

    def test_05_rechazo_de_accesos_no_autorizados_o_sin_sesion(self):
        """Verifica que operaciones sin usuario válido o con IDs cruzados sean bloqueadas."""
        # 1. Sin usuario
        res_sin_user = self.repo.guardar_exploracion(None, self.exploracion_a)
        self.assertFalse(res_sin_user.ok)
        self.assertEqual(res_sin_user.error.codigo, CODIGO_SESION_REQUERIDA)

        # 2. Usuario B intenta guardar exploración donde user_id == Usuario A
        res_cruzado = self.repo.guardar_exploracion(self.usuario_b, self.exploracion_a)
        self.assertFalse(res_cruzado.ok)
        self.assertEqual(res_cruzado.error.codigo, CODIGO_ACCESO_DENEGADO)

    def test_06_manejo_de_errores_de_conexion(self):
        """Verifica que fallos de red se traduzcan a errores controlados y reintentables."""
        self.mock_client.fallar_conexion = True
        res = self.repo.guardar_exploracion(self.usuario_a, self.exploracion_a)
        self.assertFalse(res.ok)
        self.assertEqual(res.error.codigo, CODIGO_PERSISTENCIA_FALLIDA)
        self.assertTrue(res.error.reintentable)

    def test_07_historial_vacio(self):
        """Comprueba que un usuario sin exploraciones reciba una lista vacía exitosa."""
        res = self.repo.listar_exploraciones(self.usuario_b)
        self.assertTrue(res.ok)
        self.assertEqual(res.valor, [])

    def test_08_modo_demo_aislado_en_memoria(self):
        """Verifica que el modo demo guarde en memoria local sin enviar datos a Supabase."""
        almacen_sesion_1 = {}
        repo_demo_1 = RepositorioSupabase(
            cliente_supabase=self.mock_client,
            almacen_demo=almacen_sesion_1,
        )

        exp_demo = Exploracion(
            exploracion_id=UUID("99999999-9999-9999-9999-999999999999"),
            user_id=self.usuario_demo.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[self.obj_1],
            actividades=[self.act_1],
        )

        # Guardar en demo
        res = repo_demo_1.guardar_exploracion(self.usuario_demo, exp_demo)
        self.assertTrue(res.ok)

        # Asegurar que Supabase NO haya recibido ningún registro
        self.assertEqual(len(self.mock_client.db.get("exploraciones", [])), 0)

        # Recuperar desde la misma sesión demo
        res_rec = repo_demo_1.obtener_exploracion(self.usuario_demo, exp_demo.exploracion_id)
        self.assertTrue(res_rec.ok)
        self.assertEqual(res_rec.valor.exploracion_id, exp_demo.exploracion_id)

        # Verificar que otra sesión demo distinta comience vacía (aislamiento por sesión)
        almacen_sesion_2 = {}
        repo_demo_2 = RepositorioSupabase(
            cliente_supabase=self.mock_client,
            almacen_demo=almacen_sesion_2,
        )
        res_demo_2 = repo_demo_2.listar_exploraciones(self.usuario_demo)
        self.assertTrue(res_demo_2.ok)
        self.assertEqual(len(res_demo_2.valor), 0)

    def test_09_listar_vocabulario_acumulado(self):
        """Verifica que listar_vocabulario retorne la consolidación de objetos guardados."""
        self.repo.guardar_exploracion(self.usuario_a, self.exploracion_a)
        res_voc = self.repo.listar_vocabulario(self.usuario_a)
        self.assertTrue(res_voc.ok)
        vocab = res_voc.valor
        self.assertEqual(len(vocab), 2)
        nombres = [v.nombre_en for v in vocab]
        self.assertIn("Coffee Mug", nombres)
        self.assertIn("Notebook", nombres)

    def test_10_recuperacion_sin_llamadas_a_gemini(self):
        """Asegura que el flujo de persistencia e historial no consulte a Gemini para leer datos ya guardados."""
        from unittest.mock import patch

        # Simular que si se llama a Gemini se dispare un error
        with patch("homelens.integraciones.gemini.AdaptadorGemini.analizar_imagen_exploracion") as mock_gemini:
            mock_gemini.side_effect = AssertionError("¡Gemini no debe ser llamado durante el guardado ni la recuperación!")

            # Guardar
            res_guardar = self.repo.guardar_exploracion(self.usuario_a, self.exploracion_a)
            self.assertTrue(res_guardar.ok)

            # Recuperar
            res_recup = self.repo.obtener_exploracion(self.usuario_a, self.exp_id)
            self.assertTrue(res_recup.ok)
            self.assertEqual(res_recup.valor.exploracion_id, self.exp_id)

            # Listar
            res_lista = self.repo.listar_exploraciones(self.usuario_a)
            self.assertTrue(res_lista.ok)

            # Verificar que Gemini tuvo 0 llamadas
            mock_gemini.assert_not_called()

    def test_11_token_aislado_no_mutable_entre_sesiones(self):
        """Verifica que el cliente configure la cabecera Bearer por usuario sin estado compartido mutable."""
        repo_real = RepositorioSupabase(
            supabase_url="https://ejemplo.supabase.co",
            anon_key="clave_anonima",
        )
        cliente_u_a = repo_real._obtener_cliente_para_usuario(self.usuario_a)
        cliente_u_b = repo_real._obtener_cliente_para_usuario(self.usuario_b)

        # Deben ser instancias distintas con tokens independientes
        self.assertIsNotNone(cliente_u_a)
        self.assertIsNotNone(cliente_u_b)
        self.assertNotEqual(id(cliente_u_a), id(cliente_u_b))

        auth_header_a = cliente_u_a.postgrest.headers.get("Authorization")
        auth_header_b = cliente_u_b.postgrest.headers.get("Authorization")

        self.assertEqual(auth_header_a, f"Bearer {self.usuario_a.sesion_id}")
        self.assertEqual(auth_header_b, f"Bearer {self.usuario_b.sesion_id}")

    def test_12_rechazo_usuario_no_demo_sin_jwt_valido(self):
        """Verifica que un usuario autenticado sin JWT (o con token demo) sea rechazado antes de consultar BD."""
        for token_invalido in ("", "   ", "local_demo_session"):
            usuario_sin_jwt = ContextoUsuario(
                user_id=self.user_a_id,
                sesion_id=token_invalido,
                email="alumno.a@gmail.com",
                es_demo=False,
            )
            self.assertEqual(
                self.repo.guardar_exploracion(usuario_sin_jwt, self.exploracion_a).error.codigo,
                CODIGO_SESION_REQUERIDA,
            )
            self.assertEqual(
                self.repo.obtener_exploracion(usuario_sin_jwt, self.exp_id).error.codigo,
                CODIGO_SESION_REQUERIDA,
            )
            self.assertEqual(
                self.repo.listar_exploraciones(usuario_sin_jwt).error.codigo,
                CODIGO_SESION_REQUERIDA,
            )
            self.assertEqual(
                self.repo.listar_vocabulario(usuario_sin_jwt).error.codigo,
                CODIGO_SESION_REQUERIDA,
            )

    def test_13_traduccion_error_jwt_y_rls(self):
        """Comprueba que errores de JWT expirado o rechazo RLS se traduzcan con su código específico."""
        res_jwt = self.repo._traducir_error_bd(Exception("PGRST301: JWT expired"), "Defecto")
        self.assertFalse(res_jwt.ok)
        self.assertEqual(res_jwt.error.codigo, CODIGO_SESION_REQUERIDA)
        self.assertFalse(res_jwt.error.reintentable)

        res_rls = self.repo._traducir_error_bd(
            Exception("42501: new row violates row-level security policy"), "Defecto"
        )
        self.assertFalse(res_rls.ok)
        self.assertEqual(res_rls.error.codigo, CODIGO_ACCESO_DENEGADO)
        self.assertFalse(res_rls.error.reintentable)

    def test_14_rechazo_jwt_invalido_y_rls_en_operaciones_reales(self):
        """Verifica de extremo a extremo en los métodos del repositorio errores 401/JWT y 42501/RLS."""
        from unittest.mock import MagicMock

        cliente_jwt_malo = MagicMock()
        cliente_jwt_malo.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception(
            "401 Unauthorized: Invalid JWT"
        )
        cliente_jwt_malo.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = Exception(
            "PGRST301: JWT expired"
        )
        repo_jwt_malo = RepositorioSupabase(
            supabase_url="https://test.supabase.co",
            anon_key="test_anon_key",
            cliente_supabase=cliente_jwt_malo,
        )
        res_g = repo_jwt_malo.guardar_exploracion(self.usuario_a, self.exploracion_a)
        self.assertFalse(res_g.ok)
        self.assertEqual(res_g.error.codigo, CODIGO_SESION_REQUERIDA)

        res_o = repo_jwt_malo.obtener_exploracion(self.usuario_a, self.exp_id)
        self.assertFalse(res_o.ok)
        self.assertEqual(res_o.error.codigo, CODIGO_SESION_REQUERIDA)

        cliente_rls = MagicMock()
        cliente_rls.table.return_value.select.return_value.eq.return_value.execute.return_value = MockPostgrestResponse(
            data=[]
        )
        cliente_rls.table.return_value.insert.return_value.execute.side_effect = Exception(
            "42501: new row violates row-level security policy for table exploraciones"
        )
        repo_rls = RepositorioSupabase(
            supabase_url="https://test.supabase.co",
            anon_key="test_anon_key",
            cliente_supabase=cliente_rls,
        )
        res_insert_rls = repo_rls.guardar_exploracion(self.usuario_a, self.exploracion_a)
        self.assertFalse(res_insert_rls.ok)
        self.assertEqual(res_insert_rls.error.codigo, CODIGO_ACCESO_DENEGADO)


class TestHistorialUIFuncional(unittest.TestCase):
    """Pruebas funcionales de los flujos de interfaz y aislamiento del historial (M7)."""

    def setUp(self):
        self.usuario_demo = ContextoUsuario(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            sesion_id="local_demo_session",
            email="demo@homelens.edu",
            nombre="Estudiante Demo",
            es_demo=True,
        )
        self.exp_id = UUID("77777777-7777-7777-7777-777777777777")
        self.obj_demo = ObjetoEducativo(
            objeto_id=UUID("88888888-8888-8888-8888-888888888888"),
            exploracion_id=self.exp_id,
            nombre_en="Clock",
            nombre_es="Reloj",
            recuadro=RecuadroNormalizado(ymin=10, xmin=20, ymax=100, xmax=200),
            frase_en="The clock shows the time.",
            frase_es="El reloj muestra la hora.",
        )
        self.exploracion_activa = Exploracion(
            exploracion_id=self.exp_id,
            user_id=self.usuario_demo.user_id,
            creada_en=datetime.now(timezone.utc),
            estado=EstadoAnalisis.UTILIZABLE,
            objetos=[self.obj_demo],
            actividades=[],
        )

    def test_flujo_demo_guardar_listar_recuperar_y_limpieza(self):
        """Valida guardar en sesión demo, recuperar sin imagen y purgar al cerrar sesión."""
        almacen_demo = {}
        repo = RepositorioSupabase(almacen_demo=almacen_demo)

        # 1. Guardar exploración en modo demo
        res_guardar = repo.guardar_exploracion(self.usuario_demo, self.exploracion_activa)
        self.assertTrue(res_guardar.ok)
        self.assertIn(self.exp_id, almacen_demo)

        # 2. Intentar guardar duplicada: rechazada
        res_dup = repo.guardar_exploracion(self.usuario_demo, self.exploracion_activa)
        self.assertFalse(res_dup.ok)

        # 3. Listar exploraciones en historial
        res_list = repo.listar_exploraciones(self.usuario_demo)
        self.assertTrue(res_list.ok)
        self.assertEqual(len(res_list.valor), 1)
        self.assertEqual(res_list.valor[0].exploracion_id, self.exp_id)
        self.assertEqual(res_list.valor[0].titulos_objetos, ["Clock"])

        # 4. Recuperar la exploración: conserva objetos y estructura
        res_rec = repo.obtener_exploracion(self.usuario_demo, self.exp_id)
        self.assertTrue(res_rec.ok)
        exp_recuperada = res_rec.valor
        self.assertEqual(exp_recuperada.exploracion_id, self.exp_id)
        self.assertEqual(len(exp_recuperada.objetos), 1)
        self.assertEqual(exp_recuperada.objetos[0].nombre_en, "Clock")

        # 5. Simular cierre de sesión: limpiar almacén demo de la sesión
        almacen_demo.clear()
        res_post_cierre = repo.listar_exploraciones(self.usuario_demo)
        self.assertTrue(res_post_cierre.ok)
        self.assertEqual(len(res_post_cierre.valor), 0)

    def test_formatear_fecha_local_argentina(self):
        """Convierte fechas UTC (con o sin tzinfo) a hora local America/Argentina/Buenos_Aires (ART)."""
        from homelens.ui.historial import formatear_fecha_local

        dt_utc = datetime(2026, 11, 11, 22, 37, tzinfo=timezone.utc)
        self.assertEqual(formatear_fecha_local(dt_utc), "11/11/2026 — 19:37 ART")

        dt_naive = datetime(2026, 11, 11, 22, 37)
        self.assertEqual(formatear_fecha_local(dt_naive), "11/11/2026 — 19:37 ART")

        # Cruce de medianoche: 01:15 UTC del día 12 corresponde a 22:15 ART del día 11
        dt_medianoche = datetime(2026, 11, 12, 1, 15, tzinfo=timezone.utc)
        self.assertEqual(formatear_fecha_local(dt_medianoche), "11/11/2026 — 22:15 ART")


if __name__ == "__main__":
    unittest.main()
