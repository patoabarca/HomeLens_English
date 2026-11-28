"""Cargador de política, manifiestos SKILL.md, módulos ejecutables y cliente Gemini del Agente Tutor."""

from __future__ import annotations
from dataclasses import dataclass, field
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from homelens.config import Configuracion, cargar_configuracion
from homelens.errores import (
    CODIGO_ACCESO_DENEGADO,
    CODIGO_CONFIGURACION_INVALIDA,
    CODIGO_RESPUESTA_INVALIDA,
    Resultado,
)
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import ContextoUsuario, ObjetoEducativo

DIRECTORIO_AGENTE_TUTOR = Path(__file__).resolve().parent
RUTA_POLICY_JSON = DIRECTORIO_AGENTE_TUTOR / "policy.json"
DIRECTORIO_SKILLS = DIRECTORIO_AGENTE_TUTOR / "skills"

_CACHE_MODULOS_SKILLS: Dict[str, Any] = {}


@dataclass(frozen=True)
class DefinicionSkillTutor:
    """Manifiesto en memoria cargado desde skills/<nombre>/SKILL.md."""
    name: str
    description: str
    entrypoint: str
    allowed_agents: List[str] = field(default_factory=list)
    instructions_markdown: str = ""
    file_path: str = ""


def cargar_politica_tutor(ruta_policy: Optional[Path] = None) -> Dict[str, Any]:
    """Lee y valida el archivo policy.json del Agente Tutor."""
    ruta = ruta_policy or RUTA_POLICY_JSON
    if not ruta.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de política en: {ruta}")
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(contenido, dict) or "enabled_skills" not in contenido or "limits" not in contenido:
        raise ValueError("El archivo policy.json del Agente Tutor no contiene las secciones obligatorias.")
    return contenido


def _parsear_frontmatter_skill(raw_content: str, file_path: Path) -> Dict[str, Any]:
    """Analiza de forma segura el encabezado YAML frontmatter de un SKILL.md."""
    if not raw_content.startswith("---"):
        raise ValueError(f"El archivo {file_path} no inicia con delimitador YAML '---'.")
    partes = raw_content.split("---", 2)
    if len(partes) < 3:
        raise ValueError(f"El archivo {file_path} tiene un frontmatter YAML incompleto.")

    yaml_text = partes[1].strip()
    body_text = partes[2].strip()
    meta: Dict[str, Any] = {"_body": body_text}

    lineas = yaml_text.splitlines()
    idx = 0
    while idx < len(lineas):
        linea = lineas[idx].rstrip()
        if not linea or linea.lstrip().startswith("#"):
            idx += 1
            continue
        if ":" in linea and not linea.startswith(" ") and not linea.startswith("-"):
            clave, valor = linea.split(":", 1)
            clave = clave.strip()
            valor = valor.strip()
            if valor in (">-", "|", ">"):
                idx += 1
                bloques: List[str] = []
                while idx < len(lineas) and (lineas[idx].startswith("  ") or not lineas[idx].strip()):
                    if lineas[idx].strip():
                        bloques.append(lineas[idx].strip())
                    idx += 1
                meta[clave] = " ".join(bloques)
                continue
            if valor == "":
                idx += 1
                items: List[str] = []
                while idx < len(lineas) and lineas[idx].strip().startswith("-"):
                    item = lineas[idx].strip().lstrip("-").strip()
                    if item:
                        items.append(item)
                    idx += 1
                meta[clave] = items
                continue
            meta[clave] = valor.strip("\"'")
        idx += 1
    return meta


def cargar_definicion_skill(
    nombre_skill: str,
    policy: Optional[Dict[str, Any]] = None,
    skills_root: Optional[Path] = None,
) -> DefinicionSkillTutor:
    """Verifica que la skill esté habilitada en policy.json y carga su SKILL.md."""
    pol = policy or cargar_politica_tutor()
    habilitadas = set(pol.get("enabled_skills") or [])
    if nombre_skill not in habilitadas:
        raise PermissionError(f"La skill '{nombre_skill}' no está habilitada en policy.json.")

    if not nombre_skill or "/" in nombre_skill or "\\" in nombre_skill or ".." in nombre_skill:
        raise ValueError(f"Nombre de skill inválido: '{nombre_skill}'")

    raiz = skills_root or DIRECTORIO_SKILLS
    ruta_md = (raiz / nombre_skill / "SKILL.md").resolve()
    if not ruta_md.is_relative_to(raiz.resolve()) or not ruta_md.is_file():
        raise FileNotFoundError(f"No se encontró SKILL.md para '{nombre_skill}' en {ruta_md}")

    meta = _parsear_frontmatter_skill(ruta_md.read_text(encoding="utf-8"), ruta_md)
    nombre_decl = str(meta.get("name", "")).strip()
    if nombre_decl != nombre_skill:
        raise ValueError(f"El nombre en SKILL.md ('{nombre_decl}') no coincide con '{nombre_skill}'.")

    allowed = meta.get("allowed_agents")
    allowed_list = [str(a) for a in allowed] if isinstance(allowed, list) else ([str(allowed)] if allowed else [])

    return DefinicionSkillTutor(
        name=nombre_decl,
        description=str(meta.get("description", "")).strip(),
        entrypoint=str(meta.get("entrypoint", "ejecutar.py")).strip(),
        allowed_agents=allowed_list,
        instructions_markdown=str(meta.get("_body", "")),
        file_path=str(ruta_md),
    )


def cargar_ejecutor_skill(
    nombre_skill: str,
    policy: Optional[Dict[str, Any]] = None,
) -> Any:
    """Valida SKILL.md contra policy.json y carga el módulo ejecutar.py de la skill."""
    definicion = cargar_definicion_skill(nombre_skill, policy=policy)
    ruta_py = (DIRECTORIO_SKILLS / nombre_skill / definicion.entrypoint).resolve()
    if not ruta_py.is_relative_to(DIRECTORIO_SKILLS.resolve()) or not ruta_py.is_file():
        raise FileNotFoundError(f"No se encontró el ejecutor de '{nombre_skill}' en {ruta_py}")

    clave_cache = str(ruta_py)
    if clave_cache in _CACHE_MODULOS_SKILLS:
        return _CACHE_MODULOS_SKILLS[clave_cache]

    nombre_mod = f"homelens.agente_tutor.skills.{nombre_skill.replace('-', '_')}.ejecutar"
    spec = importlib.util.spec_from_file_location(nombre_mod, str(ruta_py))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar la especificación del módulo {ruta_py}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    _CACHE_MODULOS_SKILLS[clave_cache] = modulo
    return modulo


def validar_ids_pertenecen_a_foto(
    ids_candidatos: Iterable[str],
    objetos_foto: Sequence[ObjetoEducativo],
) -> Resultado[List[str]]:
    """Comprueba que todos los identificadores pertenezcan a los objetos detectados en la foto activa."""
    ids_validos = {str(obj.objeto_id) for obj in objetos_foto}
    lista_limpia: List[str] = []
    for raw_id in ids_candidatos:
        cid = str(raw_id or "").strip()
        if not cid or cid not in ids_validos:
            return Resultado.fallo(
                codigo=CODIGO_ACCESO_DENEGADO,
                mensaje_usuario=f"Política de seguridad: el identificador '{cid}' no pertenece a los objetos de la fotografía activa.",
                reintentable=False,
            )
        if cid not in lista_limpia:
            lista_limpia.append(cid)
    return Resultado.exito(lista_limpia)


def obtener_adaptador_gemini_tutor(
    adaptador: Optional[AdaptadorGemini] = None,
    config: Optional[Configuracion] = None,
    usuario: Optional[ContextoUsuario] = None,
) -> Optional[AdaptadorGemini]:
    """Obtiene el AdaptadorGemini inyectado o construye uno con la configuración del proyecto."""
    if adaptador is not None:
        return adaptador
    cfg = config
    if cfg is None:
        res_cfg = cargar_configuracion()
        if res_cfg.ok and res_cfg.valor is not None:
            cfg = res_cfg.valor
    if cfg is None:
        return None
    return AdaptadorGemini(
        api_key=cfg.gemini_api_key,
        modelo=cfg.gemini_model,
        timeout_segundos=cfg.gemini_timeout_seconds,
        max_reintentos=cfg.gemini_max_retries,
        usuario=usuario,
    )
