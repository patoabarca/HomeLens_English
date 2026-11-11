"""Implementación de persistencia con Supabase (M7) para HomeLens English.

Utiliza una única tabla 'exploraciones' con objetos y actividades almacenados
en formato JSONB, garantizando atomicidad estricta, aislamiento mediante RLS
y soporte para sesiones en modo demostración.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from uuid import UUID

from homelens.errores import (
    Resultado,
    CODIGO_CONFIGURACION_INVALIDA,
    CODIGO_SESION_REQUERIDA,
    CODIGO_ACCESO_DENEGADO,
    CODIGO_PERSISTENCIA_FALLIDA,
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
    DesafioFindIt,
    IntentoPractica,
    Confirmacion,
)
from homelens.datos.repositorio import RepositorioHomeLens


class RepositorioSupabase(RepositorioHomeLens):
    """Repositorio concreto con cliente Supabase y Row Level Security (RLS)."""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        anon_key: Optional[str] = None,
        cliente_supabase: Optional[Any] = None,
        almacen_demo: Optional[Dict[UUID, Exploracion]] = None,
    ) -> None:
        """Inicializa el repositorio.

        Args:
            supabase_url: URL pública del proyecto Supabase.
            anon_key: Clave anónima pública (anon key) del proyecto.
            cliente_supabase: Cliente inyectado opcional (usado para pruebas y mocks).
            almacen_demo: Diccionario opcional aislado por sesión de navegador para modo demo.
        """
        self.supabase_url = (supabase_url or "").strip()
        self.anon_key = (anon_key or "").strip()
        self._cliente_inyectado = cliente_supabase
        self._almacen_demo = almacen_demo if almacen_demo is not None else {}

    @staticmethod
    def _validar_contexto_usuario(
        usuario: Optional[ContextoUsuario], mensaje_falta: str
    ) -> Optional[Resultado]:
        """Valida que exista una identidad y token JWT (o sesión demo explícita)."""
        if usuario is None or not usuario.user_id:
            return Resultado.fallo(
                codigo=CODIGO_SESION_REQUERIDA,
                mensaje_usuario=mensaje_falta,
            )
        if not usuario.es_demo:
            token = usuario.sesion_id.strip() if isinstance(usuario.sesion_id, str) else ""
            if not token or token == "local_demo_session":
                return Resultado.fallo(
                    codigo=CODIGO_SESION_REQUERIDA,
                    mensaje_usuario="Tu sesión autenticada no contiene credenciales válidas. Inicia sesión nuevamente con Google.",
                )
        return None

    @staticmethod
    def _traducir_error_bd(error: Exception, mensaje_defecto: str) -> Resultado:
        """Traduce errores de PostgREST/PostgreSQL evitando tratar fallos de JWT/RLS como errores de red."""
        msg_err = str(error).lower()
        if (
            "jwt" in msg_err
            or "pgrst301" in msg_err
            or "invalid token" in msg_err
            or "401" in msg_err
            or "unauthorized" in msg_err
        ):
            return Resultado.fallo(
                codigo=CODIGO_SESION_REQUERIDA,
                mensaje_usuario="Tu sesión expiró o no es válida. Vuelve a iniciar sesión con Google.",
                reintentable=False,
            )
        if (
            "42501" in msg_err
            or "row-level security" in msg_err
            or "permission denied" in msg_err
            or "403" in msg_err
        ):
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario="Acceso denegado por las políticas de seguridad de la base de datos.",
                reintentable=False,
            )
        return Resultado.fallo(
            codigo=CODIGO_PERSISTENCIA_FALLIDA,
            mensaje_usuario=mensaje_defecto,
            reintentable=True,
        )

    def _obtener_cliente_para_usuario(self, usuario: ContextoUsuario) -> Optional[Any]:
        """Obtiene un cliente de Supabase configurado exclusivamente para la sesión del usuario.

        Garantiza que el token JWT del usuario no sea compartido de forma mutable entre
        distintos usuarios, preservando el aislamiento estricto de sesiones.
        """
        if not usuario.es_demo:
            token_check = usuario.sesion_id.strip() if isinstance(usuario.sesion_id, str) else ""
            if not token_check or token_check == "local_demo_session":
                return None

        if self._cliente_inyectado is not None:
            # Cliente inyectado (pruebas / mocks): si tiene postgrest.auth, vincular el token
            if (
                hasattr(self._cliente_inyectado, "postgrest")
                and hasattr(self._cliente_inyectado.postgrest, "auth")
                and usuario.sesion_id
            ):
                self._cliente_inyectado.postgrest.auth(usuario.sesion_id)
            return self._cliente_inyectado

        if not self.supabase_url or not self.anon_key:
            return None

        try:
            from supabase import create_client, ClientOptions

            token_usuario = usuario.sesion_id.strip() if usuario.sesion_id else None
            headers = {}
            if token_usuario and not usuario.es_demo:
                headers["Authorization"] = f"Bearer {token_usuario}"

            opciones = ClientOptions(
                headers=headers,
                auto_refresh_token=False,
                persist_session=False,
            )
            return create_client(self.supabase_url, self.anon_key, options=opciones)
        except Exception:
            return None

    # =====================================================================
    # Serialización y Deserialización JSONB
    # =====================================================================

    @staticmethod
    def _serializar_objetos(objetos: List[ObjetoEducativo]) -> List[Dict[str, Any]]:
        """Convierte los objetos educativos a estructuras primitivas serializables en JSONB."""
        return [
            {
                "objeto_id": str(obj.objeto_id),
                "exploracion_id": str(obj.exploracion_id),
                "nombre_en": obj.nombre_en,
                "nombre_es": obj.nombre_es,
                "recuadro": {
                    "ymin": obj.recuadro.ymin,
                    "xmin": obj.recuadro.xmin,
                    "ymax": obj.recuadro.ymax,
                    "xmax": obj.recuadro.xmax,
                },
                "frase_en": obj.frase_en,
                "frase_es": obj.frase_es,
            }
            for obj in objetos
        ]

    @staticmethod
    def _serializar_actividades(actividades: List[Actividad]) -> List[Dict[str, Any]]:
        """Convierte las actividades a estructuras primitivas serializables en JSONB."""
        return [
            {
                "actividad_id": str(act.actividad_id),
                "exploracion_id": str(act.exploracion_id),
                "objeto_ids": [str(oid) for oid in act.objeto_ids],
                "pregunta": act.pregunta,
                "opciones": [
                    {"opcion_id": op.opcion_id, "texto": op.texto}
                    for op in act.opciones
                ],
                "opcion_correcta_id": act.opcion_correcta_id,
                "explicacion": act.explicacion,
            }
            for act in actividades
        ]

    @staticmethod
    def _deserializar_fila(row: Dict[str, Any]) -> Exploracion:
        """Reconstruye fielmente una Exploracion de dominio a partir del registro de BD."""
        exploracion_id = UUID(str(row["id"]))
        user_id = UUID(str(row["user_id"]))
        creada_en = (
            datetime.fromisoformat(row["creada_en"])
            if isinstance(row["creada_en"], str)
            else row["creada_en"]
        )
        estado = EstadoAnalisis(row["estado"])
        schema_version = int(row.get("schema_version", 1))

        raw_objetos = row.get("objetos") or []
        objetos: List[ObjetoEducativo] = []
        for o in raw_objetos:
            rec = o["recuadro"]
            objetos.append(
                ObjetoEducativo(
                    objeto_id=UUID(str(o["objeto_id"])),
                    exploracion_id=exploracion_id,
                    nombre_en=str(o["nombre_en"]),
                    nombre_es=str(o["nombre_es"]),
                    recuadro=RecuadroNormalizado(
                        ymin=int(rec["ymin"]),
                        xmin=int(rec["xmin"]),
                        ymax=int(rec["ymax"]),
                        xmax=int(rec["xmax"]),
                    ),
                    frase_en=str(o["frase_en"]),
                    frase_es=str(o["frase_es"]),
                )
            )

        raw_actividades = row.get("actividades") or []
        actividades: List[Actividad] = []
        for a in raw_actividades:
            opciones = [
                Opcion(opcion_id=str(op["opcion_id"]), texto=str(op["texto"]))
                for op in a.get("opciones", [])
            ]
            actividades.append(
                Actividad(
                    actividad_id=UUID(str(a["actividad_id"])),
                    exploracion_id=exploracion_id,
                    objeto_ids=[UUID(str(oid)) for oid in a.get("objeto_ids", [])],
                    pregunta=str(a["pregunta"]),
                    opciones=opciones,
                    opcion_correcta_id=str(a["opcion_correcta_id"]),
                    explicacion=str(a["explicacion"]),
                )
            )

        return Exploracion(
            exploracion_id=exploracion_id,
            user_id=user_id,
            creada_en=creada_en,
            estado=estado,
            objetos=objetos,
            actividades=actividades,
            schema_version=schema_version,
        )

    # =====================================================================
    # Métodos Públicos del Contrato RepositorioHomeLens
    # =====================================================================

    def guardar_exploracion(
        self, usuario: ContextoUsuario, exploracion: Exploracion
    ) -> Resultado[UUID]:
        """Guarda atómicamente una exploración con sus objetos y actividades en una sola operación.

        Previene duplicados por doble pulsación y valida la correspondencia de propiedad.
        """
        err_usuario = self._validar_contexto_usuario(
            usuario, "Se requiere una sesión de usuario válida para guardar exploraciones."
        )
        if err_usuario is not None:
            return err_usuario

        if exploracion is None or not exploracion.exploracion_id:
            return Resultado.fallo(
                codigo=CODIGO_PERSISTENCIA_FALLIDA,
                mensaje_usuario="Los datos de la exploración son inválidos o están vacíos.",
            )

        # Validación de propiedad estricta: un usuario solo puede guardar con su propio user_id
        if exploracion.user_id != usuario.user_id:
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario="No tienes autorización para guardar exploraciones asignadas a otro usuario.",
            )

        # Modo Demostración Local: persistencia en memoria aislada por sesión
        if usuario.es_demo:
            if exploracion.exploracion_id in self._almacen_demo:
                return Resultado.fallo(
                    codigo=CODIGO_PERSISTENCIA_FALLIDA,
                    mensaje_usuario="Esta exploración ya se encuentra guardada en tu sesión demo.",
                )
            self._almacen_demo[exploracion.exploracion_id] = exploracion
            return Resultado.exito(exploracion.exploracion_id)

        # Modo Supabase Autenticado
        cliente = self._obtener_cliente_para_usuario(usuario)
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de almacenamiento no está configurado (faltan credenciales de Supabase).",
            )

        try:
            # 1. Comprobación de duplicados previa para no sobrescribir registros existentes
            query_check = (
                cliente.table("exploraciones")
                .select("id")
                .eq("id", str(exploracion.exploracion_id))
                .execute()
            )
            registros_previos = getattr(query_check, "data", []) or []
            if registros_previos:
                return Resultado.fallo(
                    codigo=CODIGO_PERSISTENCIA_FALLIDA,
                    mensaje_usuario="La exploración ya se encuentra guardada en tu historial.",
                )

            # 2. Inserción atómica en la tabla 'exploraciones'
            fila = {
                "id": str(exploracion.exploracion_id),
                "user_id": str(usuario.user_id),
                "estado": exploracion.estado.value if hasattr(exploracion.estado, "value") else str(exploracion.estado),
                "creada_en": exploracion.creada_en.isoformat(),
                "schema_version": exploracion.schema_version,
                "objetos": self._serializar_objetos(exploracion.objetos),
                "actividades": self._serializar_actividades(exploracion.actividades),
            }

            res_insert = cliente.table("exploraciones").insert(fila).execute()
            data_insert = getattr(res_insert, "data", None)

            # Verificar que Supabase haya retornado confirmación de inserción
            if not data_insert and not getattr(res_insert, "count", None) and not isinstance(data_insert, list):
                return Resultado.fallo(
                    codigo=CODIGO_PERSISTENCIA_FALLIDA,
                    mensaje_usuario="El servidor de base de datos no confirmó la escritura de la exploración.",
                )

            return Resultado.exito(exploracion.exploracion_id)

        except Exception as e:
            # Si el error es por clave duplicada en PostgreSQL (código 23505)
            msg_err = str(e).lower()
            if "duplicate" in msg_err or "23505" in msg_err or "already exists" in msg_err:
                return Resultado.fallo(
                    codigo=CODIGO_PERSISTENCIA_FALLIDA,
                    mensaje_usuario="La exploración ya fue guardada previamente en tu historial.",
                )

            return self._traducir_error_bd(
                e,
                "No fue posible conectar con la base de datos para guardar la exploración. Intenta nuevamente.",
            )

    def obtener_exploracion(
        self, usuario: ContextoUsuario, exploracion_id: UUID
    ) -> Resultado[Exploracion]:
        """Obtiene una exploración verificando que pertenezca exclusivamente al usuario solicitante."""
        err_usuario = self._validar_contexto_usuario(
            usuario, "Se requiere una sesión válida para consultar el historial."
        )
        if err_usuario is not None:
            return err_usuario

        if not exploracion_id:
            return Resultado.fallo(
                codigo=CODIGO_PERSISTENCIA_FALLIDA,
                mensaje_usuario="Identificador de exploración inválido.",
            )

        # Modo Demostración Local
        if usuario.es_demo:
            exp_demo = self._almacen_demo.get(exploracion_id)
            if not exp_demo or exp_demo.user_id != usuario.user_id:
                return Resultado.fallo(
                    codigo=CODIGO_PERSISTENCIA_FALLIDA,
                    mensaje_usuario="La exploración solicitada no existe o no pertenece a tu sesión de prueba.",
                )
            return Resultado.exito(exp_demo)

        # Modo Supabase Autenticado
        cliente = self._obtener_cliente_para_usuario(usuario)
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de almacenamiento no está disponible.",
            )

        try:
            # Filtro doble por id y user_id (reforzado por RLS en el servidor)
            res = (
                cliente.table("exploraciones")
                .select("*")
                .eq("id", str(exploracion_id))
                .eq("user_id", str(usuario.user_id))
                .execute()
            )
            data = getattr(res, "data", []) or []
            if not data:
                return Resultado.fallo(
                    codigo=CODIGO_PERSISTENCIA_FALLIDA,
                    mensaje_usuario="La exploración solicitada no existe o no tienes permisos para acceder a ella.",
                )

            fila = data[0]
            # Doble comprobación defensiva en Python
            if str(fila.get("user_id")) != str(usuario.user_id):
                return Resultado.fallo(
                    codigo=CODIGO_ACCESO_DENEGADO,
                    mensaje_usuario="Acceso denegado: la exploración pertenece a otro usuario.",
                )

            exploracion = self._deserializar_fila(fila)
            return Resultado.exito(exploracion)

        except Exception as e:
            return self._traducir_error_bd(
                e,
                "Error al comunicarse con la base de datos al recuperar la exploración.",
            )

    def listar_exploraciones(
        self, usuario: ContextoUsuario, limite: int = 50
    ) -> Resultado[List[ResumenExploracion]]:
        """Lista los resúmenes de exploraciones guardadas por el usuario, ordenadas de más reciente a más antigua."""
        err_usuario = self._validar_contexto_usuario(
            usuario, "Se requiere una sesión válida para consultar exploraciones."
        )
        if err_usuario is not None:
            return err_usuario

        # Modo Demostración Local
        if usuario.es_demo:
            resumenes_demo: List[ResumenExploracion] = []
            for exp in sorted(
                self._almacen_demo.values(), key=lambda e: e.creada_en, reverse=True
            ):
                if exp.user_id == usuario.user_id:
                    resumenes_demo.append(
                        ResumenExploracion(
                            exploracion_id=exp.exploracion_id,
                            creada_en=exp.creada_en,
                            cantidad_objetos=len(exp.objetos),
                            titulos_objetos=[o.nombre_en for o in exp.objetos],
                        )
                    )
            return Resultado.exito(resumenes_demo[:limite])

        # Modo Supabase Autenticado
        cliente = self._obtener_cliente_para_usuario(usuario)
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de almacenamiento no está configurado.",
            )

        try:
            res = (
                cliente.table("exploraciones")
                .select("id, creada_en, objetos")
                .eq("user_id", str(usuario.user_id))
                .order("creada_en", desc=True)
                .limit(limite)
                .execute()
            )
            data = getattr(res, "data", []) or []
            resumenes: List[ResumenExploracion] = []
            for fila in data:
                raw_objs = fila.get("objetos") or []
                titulos = [str(o.get("nombre_en", "")) for o in raw_objs if o.get("nombre_en")]
                creada = (
                    datetime.fromisoformat(fila["creada_en"])
                    if isinstance(fila["creada_en"], str)
                    else fila["creada_en"]
                )
                resumenes.append(
                    ResumenExploracion(
                        exploracion_id=UUID(str(fila["id"])),
                        creada_en=creada,
                        cantidad_objetos=len(raw_objs),
                        titulos_objetos=titulos,
                    )
                )

            return Resultado.exito(resumenes)

        except Exception as e:
            return self._traducir_error_bd(
                e,
                "Error al obtener el historial de exploraciones desde la base de datos.",
            )

    def listar_vocabulario(
        self, usuario: ContextoUsuario
    ) -> Resultado[List[ObjetoEducativo]]:
        """Lista el vocabulario previamente explorado y guardado por el usuario."""
        err_usuario = self._validar_contexto_usuario(
            usuario, "Se requiere una sesión válida para consultar el vocabulario."
        )
        if err_usuario is not None:
            return err_usuario

        # Modo Demostración Local
        if usuario.es_demo:
            vocabulario_demo: List[ObjetoEducativo] = []
            vistos = set()
            for exp in self._almacen_demo.values():
                if exp.user_id == usuario.user_id:
                    for obj in exp.objetos:
                        clave = obj.nombre_en.strip().lower()
                        if clave not in vistos:
                            vistos.add(clave)
                            vocabulario_demo.append(obj)
            return Resultado.exito(vocabulario_demo)

        # Modo Supabase Autenticado
        cliente = self._obtener_cliente_para_usuario(usuario)
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de almacenamiento no está configurado.",
            )

        try:
            res = (
                cliente.table("exploraciones")
                .select("objetos")
                .eq("user_id", str(usuario.user_id))
                .order("creada_en", desc=True)
                .execute()
            )
            data = getattr(res, "data", []) or []
            vocabulario: List[ObjetoEducativo] = []
            vistos_en = set()

            for fila in data:
                raw_objs = fila.get("objetos") or []
                for o in raw_objs:
                    nom = str(o.get("nombre_en", "")).strip().lower()
                    if nom and nom not in vistos_en:
                        vistos_en.add(nom)
                        rec = o["recuadro"]
                        vocabulario.append(
                            ObjetoEducativo(
                                objeto_id=UUID(str(o["objeto_id"])),
                                exploracion_id=UUID(str(o["exploracion_id"])),
                                nombre_en=str(o["nombre_en"]),
                                nombre_es=str(o["nombre_es"]),
                                recuadro=RecuadroNormalizado(
                                    ymin=int(rec["ymin"]),
                                    xmin=int(rec["xmin"]),
                                    ymax=int(rec["ymax"]),
                                    xmax=int(rec["xmax"]),
                                ),
                                frase_en=str(o["frase_en"]),
                                frase_es=str(o["frase_es"]),
                            )
                        )

            return Resultado.exito(vocabulario)

        except Exception as e:
            return self._traducir_error_bd(
                e,
                "Error al consultar el vocabulario desde la base de datos.",
            )

    # =====================================================================
    # Métodos reservados para etapas posteriores (Tareas 10 y 12)
    # =====================================================================

    def guardar_desafio(
        self, usuario: ContextoUsuario, desafio: DesafioFindIt
    ) -> Resultado[UUID]:
        return Resultado.fallo(
            codigo=CODIGO_PERSISTENCIA_FALLIDA,
            mensaje_usuario="La persistencia de desafíos Find It corresponde a una etapa posterior.",
        )

    def obtener_desafio(
        self, usuario: ContextoUsuario, desafio_id: UUID
    ) -> Resultado[DesafioFindIt]:
        return Resultado.fallo(
            codigo=CODIGO_PERSISTENCIA_FALLIDA,
            mensaje_usuario="La obtención de desafíos Find It corresponde a una etapa posterior.",
        )

    def guardar_intento(
        self, usuario: ContextoUsuario, intento: IntentoPractica
    ) -> Resultado[Confirmacion]:
        return Resultado.fallo(
            codigo=CODIGO_PERSISTENCIA_FALLIDA,
            mensaje_usuario="El guardado de intentos de cuestionario corresponde a la Tarea 10.",
        )

    def listar_intentos(
        self, usuario: ContextoUsuario, desde: Optional[datetime] = None
    ) -> Resultado[List[IntentoPractica]]:
        return Resultado.fallo(
            codigo=CODIGO_PERSISTENCIA_FALLIDA,
            mensaje_usuario="El listado de intentos de práctica corresponde a la Tarea 10.",
        )

