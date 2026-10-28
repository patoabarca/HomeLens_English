from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, UnidentifiedImageError

try:
    from .evaluacion_common import read_csv, sha256_file
except ImportError:
    from evaluacion_common import read_csv, sha256_file


def valid_extension(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}


def validate(root: Path) -> dict:
    candidatos = root / "candidatos.csv"
    seleccion = root / "seleccion.csv"
    if not candidatos.exists():
        return {"valid": False, "errors": ["No existe candidatos.csv"], "warnings": [], "counts": {}}

    rows = read_csv(candidatos)
    ids = [row.get("open_images_id", "").strip() for row in rows]
    errors, warnings = [], []
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        errors.append("Los identificadores deben ser únicos y no vacíos")

    hashes = Counter()
    for row in rows:
        relative = row.get("ruta_relativa", "")
        if relative:
            path = root / relative
            if not path.exists():
                if row.get("estado_descarga") == "descargada":
                    errors.append(f"Falta el archivo seleccionado: {relative}")
                continue
            if not valid_extension(path):
                errors.append(f"Formato no permitido: {relative}")
                continue
            try:
                with Image.open(path) as image:
                    image.verify()
                digest = sha256_file(path)
                hashes[digest] += 1
                recorded = row.get("sha256", "")
                if recorded and recorded != digest:
                    warnings.append(f"SHA-256 diferente al registrado: {relative}")
            except (UnidentifiedImageError, OSError):
                errors.append(f"Archivo corrupto o ilegible: {relative}")

    duplicated = [digest for digest, count in hashes.items() if count > 1]
    if duplicated:
        errors.append("Se encontraron archivos duplicados exactos")

    anotaciones_path = root / "anotaciones.csv"
    if anotaciones_path.exists():
        for annotation in read_csv(anotaciones_path):
            if not annotation.get("categoria", ""):
                errors.append("Existe una anotación sin categoría")
            try:
                box = json.loads(annotation.get("bbox_homelens_yxyx", "[]"))
                if len(box) != 4 or any(value < 0 or value > 1000 for value in box):
                    raise ValueError
                ymin, xmin, ymax, xmax = box
                if ymin >= ymax or xmin >= xmax:
                    raise ValueError
            except (json.JSONDecodeError, TypeError, ValueError):
                errors.append("Existe una anotación con un bounding box HomeLens inválido")
    else:
        warnings.append("No existe anotaciones.csv")

    selected_rows = []
    if seleccion.exists():
        selected_rows = read_csv(seleccion)
        pilot_ids = {r["open_images_id"] for r in selected_rows if r.get("destino") == "piloto"}
        final_ids = {r["open_images_id"] for r in selected_rows if r.get("destino") == "evaluacion_final"}
        shared = pilot_ids.intersection(final_ids)
        if shared:
            errors.append("Hay identificadores compartidos entre piloto y evaluación final")
    else:
        warnings.append("No existe seleccion.csv; la revisión manual sigue pendiente")

    accepted = sum(1 for row in rows if row.get("aceptada", "").lower() == "si")
    counts = {"candidatas": len(rows), "aceptadas": accepted, "seleccionadas": len(selected_rows)}
    return {"valid": not errors, "errors": errors, "warnings": warnings, "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida los metadatos y archivos de A1")
    parser.add_argument("--root", type=Path, default=Path("data/evaluacion"))
    args = parser.parse_args()
    result = validate(args.root.resolve())
    print(__import__("json").dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
