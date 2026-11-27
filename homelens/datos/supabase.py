"""Implementación de persistencia con Supabase (M7) para HomeLens English.

Utiliza una única tabla 'exploraciones' con objetos y actividades almacenados
en formato JSONB, garantizando atomicidad estricta, aislamiento mediante RLS
y soporte para sesiones en modo demostración.
"""

from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Any, Dict
from uuid import UUID

from homelens.config import es_creador_autorizado, obtener_nombre_creador
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
    TipoIntento,
    ResultadoIntento,
    Confirmacion,
    RegistroConsumoIA,
    FiltroConsumoIA,
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
        almacen_intentos_demo: Optional[Dict[UUID, IntentoPractica]] = None,
    ) -> None:
        """Inicializa el repositorio.

        Args:
            supabase_url: URL pública del proyecto Supabase.
            anon_key: Clave anónima pública (anon key) del proyecto.
            cliente_supabase: Cliente inyectado opcional (usado para pruebas y mocks).
            almacen_demo: Diccionario opcional aislado por sesión de navegador para exploraciones en modo demo.
            almacen_intentos_demo: Diccionario opcional aislado por sesión de navegador para intentos en modo demo.
        """
        self.supabase_url = (supabase_url or "").strip()
        self.anon_key = (anon_key or "").strip()
        self._cliente_inyectado = cliente_supabase
        self._almacen_demo = almacen_demo if almacen_demo is not None else {}
        self._almacen_intentos_demo = (
            almacen_intentos_demo if almacen_intentos_demo is not None else {}
        )

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
        """Lista todos los objetos educativos explorados y guardados por el usuario.

        Conserva cada instancia (con su respectivo objeto_id) de palabras que aparecen en
        varias exploraciones para que el cálculo de progreso (M8) pueda vincular intentos
        asociados a cualquiera de las exploraciones y luego agrupar por palabra normalizada.
        """
        err_usuario = self._validar_contexto_usuario(
            usuario, "Se requiere una sesión válida para consultar el vocabulario."
        )
        if err_usuario is not None:
            return err_usuario

        # Modo Demostración Local
        if usuario.es_demo:
            vocabulario_demo: List[ObjetoEducativo] = []
            vistos_ids = set()
            for exp in sorted(
                self._almacen_demo.values(), key=lambda e: e.creada_en, reverse=True
            ):
                if exp.user_id == usuario.user_id:
                    for obj in exp.objetos:
                        if obj.objeto_id not in vistos_ids:
                            vistos_ids.add(obj.objeto_id)
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
            vistos_obj_ids = set()

            for fila in data:
                raw_objs = fila.get("objetos") or []
                for o in raw_objs:
                    nom = str(o.get("nombre_en", "")).strip()
                    raw_oid = o.get("objeto_id")
                    if not nom or not raw_oid:
                        continue
                    oid = UUID(str(raw_oid))
                    if oid not in vistos_obj_ids:
                        vistos_obj_ids.add(oid)
                        rec = o["recuadro"]
                        vocabulario.append(
                            ObjetoEducativo(
                                objeto_id=oid,
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

    @staticmethod
    def _serializar_intento(intento: IntentoPractica) -> Dict[str, Any]:
        """Convierte un IntentoPractica a estructura serializable para la tabla intentos_practica."""
        fecha_utc = (
            intento.fecha
            if intento.fecha.tzinfo is not None
            else intento.fecha.replace(tzinfo=timezone.utc)
        )
        return {
            "id": str(intento.intento_id),
            "user_id": str(intento.user_id),
            "tipo": intento.tipo.value if hasattr(intento.tipo, "value") else str(intento.tipo),
            "fecha": fecha_utc.isoformat(),
            "actividad_id": str(intento.actividad_id) if intento.actividad_id is not None else None,
            "desafio_id": str(intento.desafio_id) if intento.desafio_id is not None else None,
            "opcion_elegida_id": intento.opcion_elegida_id,
            "resultado": (
                intento.resultado.value
                if hasattr(intento.resultado, "value")
                else str(intento.resultado)
            ),
            "objeto_ids": [str(oid) for oid in (intento.objeto_ids or [])],
        }

    @staticmethod
    def _deserializar_intento(row: Dict[str, Any]) -> IntentoPractica:
        """Reconstruye un IntentoPractica de dominio a partir de un registro de BD."""
        intento_id = UUID(str(row["id"]))
        user_id = UUID(str(row["user_id"]))
        tipo = TipoIntento(str(row["tipo"]))
        raw_fecha = row["fecha"]
        fecha = (
            datetime.fromisoformat(raw_fecha)
            if isinstance(raw_fecha, str)
            else raw_fecha
        )
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)

        actividad_id = (
            UUID(str(row["actividad_id"]))
            if row.get("actividad_id") is not None
            else None
        )
        desafio_id = (
            UUID(str(row["desafio_id"]))
            if row.get("desafio_id") is not None
            else None
        )
        opcion_elegida_id = (
            str(row["opcion_elegida_id"])
            if row.get("opcion_elegida_id") is not None
            else None
        )
        resultado = ResultadoIntento(str(row["resultado"]))
        raw_objetos = row.get("objeto_ids") or []
        objeto_ids = [UUID(str(oid)) for oid in raw_objetos if oid]

        return IntentoPractica(
            intento_id=intento_id,
            user_id=user_id,
            tipo=tipo,
            fecha=fecha,
            actividad_id=actividad_id,
            desafio_id=desafio_id,
            opcion_elegida_id=opcion_elegida_id,
            resultado=resultado,
            objeto_ids=objeto_ids,
        )

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
        """Registra de forma idempotente un intento de práctica (Cuestionario o Find It).

        Garantiza que:
        - Cada usuario autenticado solo pueda registrar intentos con su propio user_id.
        - Un doble clic o un reintento con el mismo intento_id no duplique el registro
          y devuelva confirmación exitosa.
        - Se conserve fielmente ResultadoIntento.INDETERMINABLE como estado propio.
        """
        err_usuario = self._validar_contexto_usuario(
            usuario, "Se requiere una sesión de usuario válida para guardar intentos de práctica."
        )
        if err_usuario is not None:
            return err_usuario

        if (
            intento is None
            or not isinstance(intento, IntentoPractica)
            or not isinstance(intento.intento_id, UUID)
        ):
            return Resultado.fallo(
                codigo=CODIGO_PERSISTENCIA_FALLIDA,
                mensaje_usuario="Los datos del intento de práctica son inválidos o están incompletos.",
                reintentable=False,
            )

        if intento.user_id != usuario.user_id:
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario="No tienes autorización para guardar intentos asignados a otro usuario.",
                reintentable=False,
            )

        if not isinstance(intento.tipo, TipoIntento):
            return Resultado.fallo(
                codigo=CODIGO_PERSISTENCIA_FALLIDA,
                mensaje_usuario="El tipo de intento de práctica no es válido.",
                reintentable=False,
            )

        if not isinstance(intento.resultado, ResultadoIntento):
            return Resultado.fallo(
                codigo=CODIGO_PERSISTENCIA_FALLIDA,
                mensaje_usuario="El resultado del intento de práctica no es válido.",
                reintentable=False,
            )

        if intento.tipo == TipoIntento.CUESTIONARIO and intento.actividad_id is None:
            return Resultado.fallo(
                codigo=CODIGO_PERSISTENCIA_FALLIDA,
                mensaje_usuario="Un intento de cuestionario requiere un identificador de actividad.",
                reintentable=False,
            )

        if intento.tipo == TipoIntento.FIND_IT and intento.desafio_id is None:
            return Resultado.fallo(
                codigo=CODIGO_PERSISTENCIA_FALLIDA,
                mensaje_usuario="Un intento de Find It requiere un identificador de desafío.",
                reintentable=False,
            )

        # Modo Demostración Local: persistencia idempotente en memoria aislada por sesión
        if usuario.es_demo:
            existente = self._almacen_intentos_demo.get(intento.intento_id)
            if existente is not None:
                if existente.user_id != usuario.user_id:
                    return Resultado.fallo(
                        codigo=CODIGO_ACCESO_DENEGADO,
                        mensaje_usuario="El identificador del intento pertenece a otro usuario.",
                        reintentable=False,
                    )
                return Resultado.exito(
                    Confirmacion(
                        operacion_id=intento.intento_id,
                        mensaje="Intento de práctica ya registrado previamente en la sesión demo.",
                    )
                )
            self._almacen_intentos_demo[intento.intento_id] = intento
            return Resultado.exito(
                Confirmacion(
                    operacion_id=intento.intento_id,
                    mensaje="Intento de práctica registrado en la sesión demo.",
                )
            )

        # Modo Supabase Autenticado
        cliente = self._obtener_cliente_para_usuario(usuario)
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de almacenamiento no está configurado (faltan credenciales de Supabase).",
                reintentable=False,
            )

        try:
            # 1. Comprobación idempotente previa por intento_id
            query_check = (
                cliente.table("intentos_practica")
                .select("id, user_id")
                .eq("id", str(intento.intento_id))
                .execute()
            )
            registros_previos = getattr(query_check, "data", []) or []
            if registros_previos:
                fila_previa = registros_previos[0]
                if str(fila_previa.get("user_id")) != str(usuario.user_id):
                    return Resultado.fallo(
                        codigo=CODIGO_ACCESO_DENEGADO,
                        mensaje_usuario="No tienes autorización sobre este intento de práctica.",
                        reintentable=False,
                    )
                return Resultado.exito(
                    Confirmacion(
                        operacion_id=intento.intento_id,
                        mensaje="Intento de práctica ya registrado previamente.",
                    )
                )

            # 2. Inserción en la tabla 'intentos_practica'
            fila = self._serializar_intento(intento)
            res_insert = cliente.table("intentos_practica").insert(fila).execute()
            data_insert = getattr(res_insert, "data", None)

            if (
                not data_insert
                and not getattr(res_insert, "count", None)
                and not isinstance(data_insert, list)
            ):
                return Resultado.fallo(
                    codigo=CODIGO_PERSISTENCIA_FALLIDA,
                    mensaje_usuario="El servidor de base de datos no confirmó el guardado del intento.",
                    reintentable=True,
                )

            return Resultado.exito(
                Confirmacion(
                    operacion_id=intento.intento_id,
                    mensaje="Intento de práctica guardado exitosamente.",
                )
            )

        except Exception as e:
            msg_err = str(e).lower()
            # Idempotencia ante condición de carrera / doble clic concurrente (PostgreSQL 23505)
            if "duplicate" in msg_err or "23505" in msg_err or "already exists" in msg_err:
                return Resultado.exito(
                    Confirmacion(
                        operacion_id=intento.intento_id,
                        mensaje="Intento de práctica ya registrado previamente.",
                    )
                )

            return self._traducir_error_bd(
                e,
                "No fue posible guardar el intento de práctica en la base de datos. Puedes reintentar.",
            )

    def listar_intentos(
        self, usuario: ContextoUsuario, desde: Optional[datetime] = None
    ) -> Resultado[List[IntentoPractica]]:
        """Lista los intentos de práctica realizados por el usuario, ordenados del más reciente al más antiguo."""
        err_usuario = self._validar_contexto_usuario(
            usuario, "Se requiere una sesión válida para consultar los intentos de práctica."
        )
        if err_usuario is not None:
            return err_usuario

        desde_utc: Optional[datetime] = None
        if desde is not None:
            desde_utc = desde if desde.tzinfo is not None else desde.replace(tzinfo=timezone.utc)

        # Modo Demostración Local
        if usuario.es_demo:
            intentos_demo: List[IntentoPractica] = []
            for it in self._almacen_intentos_demo.values():
                if it.user_id != usuario.user_id:
                    continue
                fecha_it = it.fecha if it.fecha.tzinfo is not None else it.fecha.replace(tzinfo=timezone.utc)
                if desde_utc is not None and fecha_it < desde_utc:
                    continue
                intentos_demo.append(it)
            intentos_demo.sort(
                key=lambda x: x.fecha if x.fecha.tzinfo is not None else x.fecha.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            return Resultado.exito(intentos_demo)

        # Modo Supabase Autenticado
        cliente = self._obtener_cliente_para_usuario(usuario)
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_CONFIGURACION_INVALIDA,
                mensaje_usuario="El servicio de almacenamiento no está configurado.",
                reintentable=False,
            )

        try:
            query = (
                cliente.table("intentos_practica")
                .select("*")
                .eq("user_id", str(usuario.user_id))
            )
            if desde_utc is not None and hasattr(query, "gte"):
                query = query.gte("fecha", desde_utc.isoformat())

            res = query.order("fecha", desc=True).execute()
            data = getattr(res, "data", []) or []

            intentos: List[IntentoPractica] = []
            for fila in data:
                # Doble comprobación defensiva en Python además de RLS
                if str(fila.get("user_id")) != str(usuario.user_id):
                    continue
                intento = self._deserializar_intento(fila)
                if desde_utc is not None and intento.fecha < desde_utc:
                    continue
                intentos.append(intento)

            intentos.sort(key=lambda x: x.fecha, reverse=True)
            return Resultado.exito(intentos)

        except Exception as e:
            return self._traducir_error_bd(
                e,
                "Error al obtener los intentos de práctica desde la base de datos.",
            )

    # =====================================================================
    # Panel de Consumo de IA (Gemini) — Métricas y Costos Centralizados
    # =====================================================================

    def registrar_consumo_gemini(
        self, usuario: ContextoUsuario, registro: RegistroConsumoIA
    ) -> Resultado[UUID]:
        """Registra de forma idempotente una operación de consumo de Gemini."""
        val = self._validar_contexto_usuario(usuario, "Se requiere una sesión activa para registrar consumo.")
        if val is not None:
            return val

        # Modo demo: no genera registros de costos reales en Supabase
        if usuario.es_demo:
            return Resultado.exito(registro.id)

        # Para el MVP, restringir también la inserción exclusivamente a los creadores autorizados
        if not es_creador_autorizado(usuario):
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario="Acceso denegado: solo los creadores autorizados registran telemetría de consumo.",
                reintentable=False,
            )

        cliente = self._obtener_cliente_para_usuario(usuario)
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_SESION_REQUERIDA,
                mensaje_usuario="No se pudo obtener cliente autenticado para registrar consumo.",
            )

        try:
            fila = {
                "id": str(registro.id),
                "operacion_id": str(registro.operacion_id),
                "user_id": str(usuario.user_id),
                "fecha": registro.fecha.isoformat(),
                "modelo": registro.modelo,
                "estado": registro.estado,
                "duracion_ms": int(registro.duracion_ms),
                "numero_llamadas": int(registro.numero_llamadas),
                "numero_reintentos": int(registro.numero_reintentos),
                "codigo_error": registro.codigo_error,
                "prompt_tokens": registro.prompt_tokens,
                "candidates_tokens": registro.candidates_tokens,
                "thoughts_tokens": registro.thoughts_tokens,
                "total_tokens": registro.total_tokens,
                "cached_tokens": registro.cached_tokens,
                "tarifa_version": registro.tarifa_version,
                "costo_estimado": str(registro.costo_estimado) if registro.costo_estimado is not None else None,
                "metadatos": registro.metadatos or {},
            }

            # Inserción idempotente e inmutable (ON CONFLICT DO NOTHING en Postgres):
            # Se utiliza ignore_duplicates=True para que PostgREST no requiera permisos de UPDATE.
            cliente.table("consumo_gemini").upsert(
                fila, on_conflict="operacion_id", ignore_duplicates=True
            ).execute()

            return Resultado.exito(registro.id)

        except Exception as e:
            return self._traducir_error_bd(
                e,
                "Error al registrar métricas de consumo en la base de datos.",
            )

    def consultar_consumo_gemini(
        self,
        usuario: ContextoUsuario,
        filtro: Optional[FiltroConsumoIA] = None,
    ) -> Resultado[List[RegistroConsumoIA]]:
        """Consulta registros de consumo de Gemini si el usuario es un creador autorizado."""
        val = self._validar_contexto_usuario(usuario, "Se requiere una sesión activa para consultar el consumo.")
        if val is not None:
            return val

        # Verificación estricta del lado del servidor: sólo creadores autorizados
        if usuario.es_demo or not es_creador_autorizado(usuario):
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario="Acceso denegado: el panel de consumo es exclusivo para los creadores autorizados.",
                reintentable=False,
            )

        cliente = self._obtener_cliente_para_usuario(usuario)
        if cliente is None:
            return Resultado.fallo(
                codigo=CODIGO_SESION_REQUERIDA,
                mensaje_usuario="No se pudo obtener cliente autenticado para consultar consumo.",
            )

        try:
            query = cliente.table("consumo_gemini").select("*").order("fecha", desc=True)

            if filtro:
                if filtro.user_id:
                    query = query.eq("user_id", str(filtro.user_id))
                if filtro.modelo:
                    query = query.eq("modelo", filtro.modelo)
                if filtro.estado:
                    query = query.eq("estado", filtro.estado)
                if filtro.fecha_desde:
                    query = query.gte("fecha", filtro.fecha_desde.isoformat())
                if filtro.fecha_hasta:
                    query = query.lte("fecha", filtro.fecha_hasta.isoformat())

            resp = query.execute()
            filas = resp.data or []

            registros: List[RegistroConsumoIA] = []
            for f in filas:
                f_uid = UUID(str(f["user_id"]))
                costo_dec = Decimal(str(f["costo_estimado"])) if f.get("costo_estimado") is not None else None
                fecha_val = datetime.fromisoformat(str(f["fecha"]))
                if fecha_val.tzinfo is None:
                    fecha_val = fecha_val.replace(tzinfo=timezone.utc)

                registros.append(
                    RegistroConsumoIA(
                        id=UUID(str(f["id"])),
                        operacion_id=UUID(str(f["operacion_id"])),
                        user_id=f_uid,
                        fecha=fecha_val,
                        modelo=str(f.get("modelo", "")),
                        estado=str(f.get("estado", "")),
                        duracion_ms=int(f.get("duracion_ms", 0)),
                        numero_llamadas=int(f.get("numero_llamadas", 1)),
                        numero_reintentos=int(f.get("numero_reintentos", 0)),
                        codigo_error=int(f["codigo_error"]) if f.get("codigo_error") is not None else None,
                        prompt_tokens=int(f["prompt_tokens"]) if f.get("prompt_tokens") is not None else None,
                        candidates_tokens=int(f["candidates_tokens"]) if f.get("candidates_tokens") is not None else None,
                        thoughts_tokens=int(f["thoughts_tokens"]) if f.get("thoughts_tokens") is not None else None,
                        total_tokens=int(f["total_tokens"]) if f.get("total_tokens") is not None else None,
                        cached_tokens=int(f["cached_tokens"]) if f.get("cached_tokens") is not None else None,
                        tarifa_version=f.get("tarifa_version"),
                        costo_estimado=costo_dec,
                        integrante_etiqueta=obtener_nombre_creador(f_uid),
                        metadatos=f.get("metadatos"),
                    )
                )

            return Resultado.exito(registros)

        except Exception as e:
            return self._traducir_error_bd(
                e,
                "Error al consultar métricas de consumo desde la base de datos.",
            )

