"""Lectura de A1 y metadatos experimentales, sin reescribir archivos de CVAT."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .evaluacion_common import read_csv, sha256_file

PROYECTO = Path(__file__).resolve().parents[2]


def dentro(path: Path, root: Path) -> Path:
    path, root = path.resolve(), root.resolve()
    if not path.is_relative_to(root):
        raise ValueError("Ruta fuera del directorio autorizado")
    return path


def identificador(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", value):
        raise ValueError("Identificador inseguro o vacío")
    return value


def guardar_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporal = path.with_suffix(path.suffix + ".tmp")
    temporal.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporal.replace(path)


def preparar_manifest(root: Path, fotos_root: Path, conjunto: str, origen: str = "pendiente") -> dict:
    """Sólo lee metadatos. No abre las fotografías reservadas del conjunto final."""
    root = dentro(root, PROYECTO)
    fotos_root = dentro(fotos_root, PROYECTO)
    if conjunto not in {"piloto", "evaluacion_final"}:
        raise ValueError("Conjunto desconocido")
    if origen not in {"real", "sintetica", "pendiente"}:
        raise ValueError("Procedencia desconocida")
    candidates = read_csv(root / "candidatos.csv")
    annotations = read_csv(root / "anotaciones.csv")
    if not candidates or len({r["image_id"] for r in candidates}) != len(candidates):
        raise ValueError("Dataset vacío o IDs repetidos")
    known = {r["image_id"] for r in candidates}
    if len({r.get("sha256") for r in candidates}) != len(candidates):
        raise ValueError("Fotografías duplicadas por hash")
    annotation_ids = [r["cvat_annotation_id"] for r in annotations]
    if len(set(annotation_ids)) != len(annotation_ids) or any(not a for a in annotation_ids):
        raise ValueError("IDs de anotaciones CVAT vacíos o repetidos")
    from .metricas import validar_box
    for row in annotations:
        if row["image_id"] not in known or not row["categoria"].strip():
            raise ValueError("Anotación huérfana o sin categoría")
        validar_box(json.loads(row["bbox_homelens_yxyx"]))
    selection = root / "seleccion.csv"
    if selection.exists():
        rows = read_csv(selection)
        if len({r["image_id"] for r in rows}) != len(rows):
            raise ValueError("Selección con IDs duplicados")
        for row in rows:
            if row["image_id"] not in known or row.get("destino") != conjunto:
                raise ValueError("Selección incompatible con el conjunto")
    images = []
    for row in candidates:
        identificador(row["image_id"])
        accepted = row.get("aceptada")
        if (
            row.get("fuente") != "CVAT"
            or row.get("destino") != conjunto
            or accepted not in {"si", "pendiente"}
            or (accepted == "pendiente" and conjunto != "evaluacion_final")
        ):
            raise ValueError("Se requieren fotografías CVAT del conjunto solicitado; las finales pueden seguir pendientes de revisión")
        if not re.fullmatch(r"[a-f0-9]{64}", row.get("sha256", "")):
            raise ValueError("Falta hash de imagen en A1")
        if not row.get("ruta_relativa"):
            raise ValueError("Falta ruta de fotografía")
        dentro(root / row["ruta_relativa"], fotos_root)
        refs = [r for r in annotations if r["image_id"] == row["image_id"]]
        if int(row["cantidad_objetos"]) != len(refs):
            raise ValueError("Cantidad de objetos incompatible con A1")
        images.append({"image_id": row["image_id"], "sha256": row["sha256"],
                       "origen": origen, "permisos": "pendiente", "exhaustiva": False,
                       "revision_humana": "aprobada" if accepted == "si" else "pendiente"})
    files = ["candidatos.csv", "anotaciones.csv", "imagenes_normalizadas.json", "procedencia.json", "seleccion.csv"]
    return {"version": 1, "conjunto": conjunto, "root": str(root.relative_to(PROYECTO)),
            "fotos_root": str(fotos_root.relative_to(PROYECTO)),
            "archivos_a1": {name: sha256_file(root / name) for name in files if (root / name).exists()},
            "imagenes": images}


def cargar_dataset(manifest_path: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    current = preparar_manifest(PROYECTO / manifest["root"], PROYECTO / manifest["fotos_root"], manifest["conjunto"])
    if current["archivos_a1"] != manifest["archivos_a1"]:
        raise ValueError("A1 cambió desde la preparación del manifiesto")
    if [(x["image_id"], x["sha256"]) for x in current["imagenes"]] != [(x["image_id"], x["sha256"]) for x in manifest["imagenes"]]:
        raise ValueError("Imágenes incompatibles con A1")
    for image in manifest["imagenes"]:
        if image["origen"] not in {"real", "sintetica", "pendiente"} or type(image["exhaustiva"]) is not bool:
            raise ValueError("Metadatos de revisión inválidos")
        if image.get("revision_humana", "aprobada") not in {"pendiente", "aprobada"}:
            raise ValueError("Estado de revisión humana inválido")
    return manifest, read_csv(PROYECTO / manifest["root"] / "anotaciones.csv")


def fotografia(manifest: dict, image: dict) -> Path:
    root = PROYECTO / manifest["root"]
    row = next(r for r in read_csv(root / "candidatos.csv") if r["image_id"] == image["image_id"])
    return dentro(root / row["ruta_relativa"], PROYECTO / manifest["fotos_root"])
