"""Módulo M8: Consulta y cálculo del progreso pedagógico (Parte 13).

Funciones para consolidar el vocabulario explorado y practicado y las
estadísticas de aciertos separadas por tipo de actividad (Cuestionarios y Find It),
conservando INDETERMINABLE como resultado propio excluido del conteo de errores
y del denominador del porcentaje de aciertos.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid5, NAMESPACE_DNS

from homelens.config import Configuracion, cargar_configuracion
from homelens.datos.repositorio import RepositorioHomeLens
from homelens.datos.supabase import RepositorioSupabase
from homelens.errores import CODIGO_SESION_REQUERIDA, Resultado
from homelens.modelos import (
    ContextoUsuario,
    EstadoPalabra,
    IntentoPractica,
    ObjetoEducativo,
    PalabraResumen,
    ResultadoIntento,
    ResumenProgreso,
    TipoIntento,
)
from homelens.practicas import _DESAFIOS_PREDETERMINADOS_FIND_IT


def _normalizar_palabra(nombre_en: str) -> str:
    """Normaliza el nombre en inglés para agrupar apariciones repetidas de una misma palabra."""
    return " ".join((nombre_en or "").strip().lower().split())


def _mapa_objetos_base_find_it() -> Dict[str, Tuple[str, str, str]]:
    """Construye el mapa {str(objeto_base_id): (clave_normalizada, nombre_en, nombre_es)} del vocabulario base de Find It."""
    mapa: Dict[str, Tuple[str, str, str]] = {}
    for nombre_en, nombre_es in _DESAFIOS_PREDETERMINADOS_FIND_IT:
        clave = _normalizar_palabra(nombre_en)
        if not clave:
            continue
        objeto_base_id = uuid5(NAMESPACE_DNS, f"homelens:objeto_base:{clave}")
        mapa[str(objeto_base_id)] = (clave, nombre_en.strip(), nombre_es.strip())
    return mapa


def _normalizar_fecha_utc(fecha: datetime) -> datetime:
    """Garantiza que una fecha tenga zona horaria UTC para comparaciones seguras."""
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


def _calcular_porcentaje(aciertos: int, evaluables: int) -> Optional[float]:
    """Calcula el porcentaje de aciertos sobre intentos evaluables.

    Si no existen intentos evaluables (evaluables == 0), devuelve None para no
    inventar un porcentaje de 0% o 100%.
    """
    if evaluables <= 0:
        return None
    return round((aciertos / evaluables) * 100.0, 2)


def calcular_progreso(
    vocabulario: List[ObjetoEducativo],
    intentos: List[IntentoPractica],
) -> ResumenProgreso:
    """Calcula el progreso formativo del estudiante de forma pura.

    Reglas del dominio (M8 - Parte 13):
    1. Agrupa las palabras exploradas por nombre normalizado en inglés (`nombre_en`),
       evitando duplicados cuando una palabra aparece en varias exploraciones.
    2. Una palabra explorada pasa a estado `PRACTICADA` únicamente cuando está
       vinculada a un intento evaluable (`CORRECTO` o `INCORRECTO`), ya sea por
       su `objeto_id` de cualquiera de las exploraciones guardadas o por un desafío
       Find It del vocabulario base para esa misma palabra. Conserva la fecha más
       reciente como `ultima_practica` y repetir prácticas sobre la misma palabra
       no la duplica.
    3. Las palabras identificables de Find It del vocabulario base (`homelens:objeto_base:<clave>`)
       con intento evaluable se suman a `total_palabras_practicadas` y `palabras_practicadas`
       sin agregarlas a `palabras_exploradas`. Si la palabra también fue explorada en una
       fotografía guardada, se cuenta una única vez (en `palabras_exploradas` con estado `PRACTICADA`).
    4. Los intentos de cuestionarios sobre exploraciones que el usuario no guardó en su historial
       conservan en `intentos_practica` únicamente el `objeto_id` (UUID aleatorio generado al
       analizar la foto) y el `actividad_id`, sin almacenar el texto de la palabra en la tabla
       `intentos_practica`. Como ese `objeto_id` no puede resolverse a un nombre de palabra sin
       la exploración guardada, el intento se mantiene íntegramente en las estadísticas de
       cuestionarios (`total_intentos`, `cuestionarios_correctos`, `cuestionarios_incorrectos`,
       porcentajes y `objetos_no_resueltos_count`), sin inventar una palabra en el vocabulario.
    5. `INDETERMINABLE` se conserva como resultado propio de Find It:
       - No cambia el estado de una palabra a `PRACTICADA` ni suma a `total_palabras_practicadas`.
       - No suma al conteo de errores (`find_it_no_encontrados`).
       - Se excluye del denominador del porcentaje de aciertos (`find_it_evaluables`
         y `total_evaluables`). Si todos los intentos son indeterminables, los
         porcentajes de aciertos devuelven `None`.
    """
    mapa_base_id = _mapa_objetos_base_find_it()
    catalogo_base_por_clave: Dict[str, Tuple[str, str]] = {
        clave: (nom_en, nom_es) for (clave, nom_en, nom_es) in mapa_base_id.values()
    }

    # Mapeo de práctica evaluable por objeto_id específico y por clave de palabra base
    objetos_practicados_por_id: Dict[str, datetime] = {}
    claves_practicadas_por_base: Dict[str, datetime] = {}

    cuestionarios_correctos = 0
    cuestionarios_incorrectos = 0
    find_it_encontrados = 0
    find_it_no_encontrados = 0
    find_it_indeterminables = 0

    lista_vocabulario = vocabulario or []
    lista_intentos = intentos or []

    for intento in lista_intentos:
        tipo_val = intento.tipo.value if isinstance(intento.tipo, TipoIntento) else str(intento.tipo)
        fecha_intento = _normalizar_fecha_utc(intento.fecha)

        if tipo_val == TipoIntento.CUESTIONARIO.value:
            if intento.resultado == ResultadoIntento.CORRECTO:
                cuestionarios_correctos += 1
            elif intento.resultado == ResultadoIntento.INCORRECTO:
                cuestionarios_incorrectos += 1
        elif tipo_val == TipoIntento.FIND_IT.value:
            if intento.resultado == ResultadoIntento.CORRECTO:
                find_it_encontrados += 1
            elif intento.resultado == ResultadoIntento.INCORRECTO:
                find_it_no_encontrados += 1
            elif intento.resultado == ResultadoIntento.INDETERMINABLE:
                find_it_indeterminables += 1

        # Solo los intentos evaluables (CORRECTO o INCORRECTO) marcan vocabulario como PRACTICADA
        if intento.resultado in (ResultadoIntento.CORRECTO, ResultadoIntento.INCORRECTO):
            for obj_id in (intento.objeto_ids or []):
                str_id = str(obj_id)
                prev_fecha = objetos_practicados_por_id.get(str_id)
                if prev_fecha is None or fecha_intento > prev_fecha:
                    objetos_practicados_por_id[str_id] = fecha_intento

                info_base = mapa_base_id.get(str_id)
                if info_base is not None:
                    clave_base = info_base[0]
                    prev_base = claves_practicadas_por_base.get(clave_base)
                    if prev_base is None or fecha_intento > prev_base:
                        claves_practicadas_por_base[clave_base] = fecha_intento

    # 1. Consolidar palabras exploradas agrupando repeticiones del mismo nombre normalizado
    palabras_dict: Dict[str, PalabraResumen] = {}
    ids_objetos_explorados_guardados: set[str] = set()

    for obj in lista_vocabulario:
        ids_objetos_explorados_guardados.add(str(obj.objeto_id))
        clave = _normalizar_palabra(obj.nombre_en)
        if not clave:
            continue

        fechas_candidatas: List[datetime] = []
        fecha_por_id = objetos_practicados_por_id.get(str(obj.objeto_id))
        if fecha_por_id is not None:
            fechas_candidatas.append(fecha_por_id)

        fecha_por_base = claves_practicadas_por_base.get(clave)
        if fecha_por_base is not None:
            fechas_candidatas.append(fecha_por_base)

        ultima_fecha_obj: Optional[datetime] = max(fechas_candidatas) if fechas_candidatas else None
        fue_practicada = ultima_fecha_obj is not None

        if clave not in palabras_dict:
            palabras_dict[clave] = PalabraResumen(
                nombre_en=obj.nombre_en.strip(),
                nombre_es=obj.nombre_es.strip(),
                estado=EstadoPalabra.PRACTICADA if fue_practicada else EstadoPalabra.EXPLORADA,
                ultima_practica=ultima_fecha_obj,
            )
        else:
            actual = palabras_dict[clave]
            fechas_acumuladas = [
                f for f in (actual.ultima_practica, ultima_fecha_obj) if f is not None
            ]
            mejor_fecha = max(fechas_acumuladas) if fechas_acumuladas else None
            nuevo_estado = (
                EstadoPalabra.PRACTICADA
                if (actual.estado == EstadoPalabra.PRACTICADA or fue_practicada)
                else EstadoPalabra.EXPLORADA
            )
            palabras_dict[clave] = PalabraResumen(
                nombre_en=actual.nombre_en,
                nombre_es=actual.nombre_es,
                estado=nuevo_estado,
                ultima_practica=mejor_fecha,
            )

    # 2. Identificar palabras practicadas del vocabulario base de Find It que no están en palabras_exploradas
    palabras_base_practicadas: List[PalabraResumen] = []
    for clave_base, fecha_practica_base in claves_practicadas_por_base.items():
        if clave_base in palabras_dict:
            # Ya está incluida y marcada como PRACTICADA dentro de palabras_exploradas (no duplicar)
            continue
        nom_en, nom_es = catalogo_base_por_clave[clave_base]
        palabras_base_practicadas.append(
            PalabraResumen(
                nombre_en=nom_en,
                nombre_es=nom_es,
                estado=EstadoPalabra.PRACTICADA,
                ultima_practica=fecha_practica_base,
            )
        )

    # 3. Contabilizar objeto_ids de intentos evaluables cuya exploración no fue guardada
    # (solo queda el UUID en intentos_practica y no pertenece a exploraciones guardadas ni al catálogo base)
    ids_no_resueltos = {
        oid
        for oid in objetos_practicados_por_id
        if oid not in ids_objetos_explorados_guardados and oid not in mapa_base_id
    }

    cuestionarios_total = cuestionarios_correctos + cuestionarios_incorrectos
    cuestionarios_evaluables = cuestionarios_total
    cuestionarios_porcentaje = _calcular_porcentaje(
        cuestionarios_correctos, cuestionarios_evaluables
    )

    find_it_evaluables = find_it_encontrados + find_it_no_encontrados
    find_it_total = find_it_evaluables + find_it_indeterminables
    find_it_porcentaje = _calcular_porcentaje(find_it_encontrados, find_it_evaluables)

    total_aciertos_evaluables = cuestionarios_correctos + find_it_encontrados
    total_errores_evaluables = cuestionarios_incorrectos + find_it_no_encontrados
    total_evaluables = cuestionarios_evaluables + find_it_evaluables
    porcentaje_global = _calcular_porcentaje(total_aciertos_evaluables, total_evaluables)

    total_exploradas_practicadas = sum(
        1 for p in palabras_dict.values() if p.estado == EstadoPalabra.PRACTICADA
    )
    total_palabras_practicadas = total_exploradas_practicadas + len(palabras_base_practicadas)

    resultados_por_tipo: Dict[str, Any] = {
        # Claves base de compatibilidad
        "cuestionarios_correctos": cuestionarios_correctos,
        "cuestionarios_incorrectos": cuestionarios_incorrectos,
        "find_it_encontrados": find_it_encontrados,
        "find_it_no_encontrados": find_it_no_encontrados,
        "find_it_indeterminables": find_it_indeterminables,
        # Métricas desglosadas para la pantalla Mi Progreso (Parte 14)
        "cuestionarios_total": cuestionarios_total,
        "cuestionarios_evaluables": cuestionarios_evaluables,
        "cuestionarios_porcentaje_aciertos": cuestionarios_porcentaje,
        "find_it_total": find_it_total,
        "find_it_evaluables": find_it_evaluables,
        "find_it_porcentaje_aciertos": find_it_porcentaje,
        "total_evaluables": total_evaluables,
        "total_aciertos_evaluables": total_aciertos_evaluables,
        "total_errores_evaluables": total_errores_evaluables,
        "porcentaje_aciertos_evaluables": porcentaje_global,
        # Conteo de palabras practicadas (exploradas + vocabulario base de Find It) y objetos sin exploración guardada
        "palabras_exploradas_practicadas_count": total_exploradas_practicadas,
        "palabras_base_practicadas_count": len(palabras_base_practicadas),
        "total_palabras_practicadas": total_palabras_practicadas,
        "palabras_base_practicadas": palabras_base_practicadas,
        "objetos_no_resueltos_count": len(ids_no_resueltos),
    }

    return ResumenProgreso(
        palabras_exploradas=list(palabras_dict.values()),
        total_intentos=len(lista_intentos),
        resultados_por_tipo=resultados_por_tipo,
    )


def _construir_repositorio_por_defecto(
    config: Optional[Configuracion] = None,
) -> RepositorioHomeLens:
    """Instancia RepositorioSupabase conectando los almacenes de sesión si Streamlit está activo."""
    cfg = config
    if cfg is None:
        res_cfg = cargar_configuracion()
        cfg = res_cfg.valor if res_cfg.ok else None

    almacen_demo = None
    almacen_intentos_demo = None
    try:
        import streamlit as st

        almacen_demo = st.session_state.get("_exploraciones_demo")
        almacen_intentos_demo = st.session_state.get("_intentos_demo")
    except Exception:
        pass

    tiene_sb = bool(cfg and cfg.tiene_supabase)
    return RepositorioSupabase(
        supabase_url=cfg.supabase_url if tiene_sb and cfg else None,
        anon_key=cfg.supabase_anon_key if tiene_sb and cfg else None,
        almacen_demo=almacen_demo,
        almacen_intentos_demo=almacen_intentos_demo,
    )


def obtener_progreso(
    usuario: ContextoUsuario,
    repositorio: Optional[RepositorioHomeLens] = None,
    config: Optional[Configuracion] = None,
) -> Resultado[ResumenProgreso]:
    """Consulta el vocabulario e intentos del usuario en el repositorio y calcula su ResumenProgreso.

    - Si el usuario aún no tiene actividad, devuelve un ResumenProgreso vacío válido.
    - Si falla `listar_vocabulario` o `listar_intentos`, propaga el `Resultado` de error
      para que la pantalla «Mi Progreso» (Parte 14) pueda mostrarlo.
    - Soporta tanto sesiones autenticadas en Supabase como el modo demostración local.
    """
    if usuario is None or not isinstance(usuario, ContextoUsuario) or not usuario.user_id:
        return Resultado.fallo(
            codigo=CODIGO_SESION_REQUERIDA,
            mensaje_usuario="Debes iniciar sesión para consultar tu progreso.",
            reintentable=False,
        )

    repo = repositorio if repositorio is not None else _construir_repositorio_por_defecto(config=config)

    res_vocab = repo.listar_vocabulario(usuario)
    if not res_vocab.ok:
        return Resultado(ok=False, valor=None, error=res_vocab.error)

    res_intentos = repo.listar_intentos(usuario)
    if not res_intentos.ok:
        return Resultado(ok=False, valor=None, error=res_intentos.error)

    resumen = calcular_progreso(
        vocabulario=res_vocab.valor or [],
        intentos=res_intentos.valor or [],
    )
    return Resultado.exito(resumen)


def consultar_progreso_usuario(
    usuario: ContextoUsuario,
    repositorio: Optional[RepositorioHomeLens] = None,
    config: Optional[Configuracion] = None,
) -> Resultado[ResumenProgreso]:
    """Alias descriptivo de `obtener_progreso` para consumo directo desde la vista «Mi Progreso» (Parte 14)."""
    return obtener_progreso(usuario=usuario, repositorio=repositorio, config=config)
