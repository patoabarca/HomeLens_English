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


def row_id(row: dict) -> str:
    return (row.get("image_id") or row.get("open_images_id") or "").strip()


def validate(root: Path) -> dict:
    candidatos = root / "candidatos.csv"
    seleccion = root / "seleccion.csv"
    if not candidatos.exists():
        return {"valid": False, "errors": ["No existe candidatos.csv"], "warnings": [], "counts": {}}

    rows = read_csv(candidatos)
    ids = [row_id(row) for row in rows]
    errors, warnings = [], []
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        errors.append("Los identificadores deben ser únicos y no vacíos")

    hashes = Counter()
    normalized_meta = root / "imagenes_normalizadas.json"
    normalized_metadata = {}
    if normalized_meta.exists():
        normalized_metadata = {
            str(item["file_name"]): item
            for item in json.loads(normalized_meta.read_text(encoding="utf-8"))
        }
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
                    if row.get("fuente", "").upper() == "CVAT":
                        declared_name = row.get("nombre_archivo", "")
                        if declared_name in normalized_metadata:
                            expected_width = int(normalized_metadata[declared_name]["width"])
                            expected_height = int(normalized_metadata[declared_name]["height"])
                            with Image.open(path) as readable_image:
                                actual = (readable_image.width, readable_image.height)
                                actual_format = readable_image.format
                            expected = (expected_width, expected_height)
                            if actual != expected:
                                transformation = normalized_metadata[declared_name].get(
                                    "transformacion_validada"
                                )
                                cocow = int(transformation.get("coco_width", 0)) if isinstance(transformation, dict) else 0
                                cocoh = int(transformation.get("coco_height", 0)) if isinstance(transformation, dict) else 0
                                actualw = int(transformation.get("actual_width", 0)) if isinstance(transformation, dict) else 0
                                actualh = int(transformation.get("actual_height", 0)) if isinstance(transformation, dict) else 0
                                ratio_difference = float(transformation.get("ratio_difference", -1)) if isinstance(transformation, dict) else -1
                                valid_transform = (
                                    transformation is not None
                                    and transformation.get("method") == "uniform_resize_same_aspect_ratio"
                                    and transformation.get("visual_review_accepted") is True
                                    and (cocow, cocoh) == (expected_width, expected_height)
                                    and (actualw, actualh) == actual
                                    and 0 <= ratio_difference <= 0.001
                                )
                                if not valid_transform:
                                    errors.append(
                                        f"Dimensiones distintas para {declared_name}: "
                                        f"exportación={expected_width}x{expected_height}, "
                                        f"real={actual[0]}x{actual[1]}"
                                    )
                                else:
                                    warnings.append(
                                        f"Transformación validada para {declared_name}: "
                                        f"COCO={cocow}x{cocoh}, real={actualw}x{actualh}, "
                                        "misma relación de aspecto."
                                    )
                            declared_suffix = Path(declared_name).suffix.lower()
                            format_suffix = {
                                "JPEG": ".jpg",
                                "PNG": ".png",
                                "WEBP": ".webp",
                            }.get(actual_format)
                            if format_suffix and declared_suffix not in {format_suffix, ".jpeg"}:
                                warnings.append(
                                    f"Extensión/formato distinto para {declared_name}: "
                                    f"declarado={declared_suffix}, real={format_suffix}"
                                )
                digest = sha256_file(path)
                hashes[digest] += 1
                recorded = row.get("sha256", "")
                if recorded and recorded != digest:
                    warnings.append(f"SHA-256 diferente al registrado: {relative}")
            except (UnidentifiedImageError, OSError):
                errors.append(f"Archivo corrupto o ilegible: {relative}")
        elif row.get("fuente", "").upper() == "CVAT":
            original_name = row.get("nombre_archivo", "")
            if original_name:
                warnings.append(
                    f"Faltan las fotografías originales del piloto: {original_name}"
                )

    original_dir = root / "fotografias_originales"
    if original_dir.exists():
        normalized_meta = root / "imagenes_normalizadas.json"
        metadata = {}
        if normalized_meta.exists():
            metadata = {
                str(item["file_name"]): item
                for item in json.loads(normalized_meta.read_text(encoding="utf-8"))
            }
        for original in original_dir.rglob("*"):
            if original.is_file() and valid_extension(original):
                digest = sha256_file(original)
                hashes[digest] += 1
                if original.name in metadata:
                    try:
                        with Image.open(original) as image:
                            actual = (image.width, image.height)
                        expected = (
                            int(metadata[original.name]["width"]),
                            int(metadata[original.name]["height"]),
                        )
                        if actual != expected:
                            errors.append(
                                f"Dimensiones distintas para {original.name}: "
                                f"exportación={expected[0]}x{expected[1]}, real={actual[0]}x{actual[1]}"
                            )
                    except (UnidentifiedImageError, OSError):
                        errors.append(f"Fotografía original corrupta: {original.name}")

    duplicated = [digest for digest, count in hashes.items() if count > 1]
    if duplicated:
        errors.append("Se encontraron archivos duplicados exactos")

    anotaciones_path = root / "anotaciones.csv"
    if anotaciones_path.exists():
        annotation_counts = Counter()
        for annotation in read_csv(anotaciones_path):
            annotation_counts[row_id(annotation)] += 1
            if not annotation.get("categoria", ""):
                errors.append("Existe una anotación sin categoría")
            if not row_id(annotation):
                errors.append("Existe una anotación sin identificador de fotografía")
            try:
                box = json.loads(annotation.get("bbox_homelens_yxyx", "[]"))
                if len(box) != 4 or any(value < 0 or value > 1000 for value in box):
                    raise ValueError
                ymin, xmin, ymax, xmax = box
                if ymin >= ymax or xmin >= xmax:
                    raise ValueError
            except (json.JSONDecodeError, TypeError, ValueError):
                errors.append("Existe una anotación con un bounding box HomeLens inválido")
        for row in rows:
            recorded = row.get("cantidad_objetos", "")
            if recorded:
                try:
                    if int(recorded) != annotation_counts[row_id(row)]:
                        errors.append(
                            f"cantidad_objetos no coincide con las anotaciones: {row_id(row)}"
                        )
                except ValueError:
                    errors.append(f"cantidad_objetos inválida: {row['open_images_id']}")
    else:
        warnings.append("No existe anotaciones.csv")

    selected_rows = []
    if seleccion.exists():
        selected_rows = read_csv(seleccion)
        pilot_ids = {row_id(r) for r in selected_rows if r.get("destino") == "piloto"}
        final_ids = {row_id(r) for r in selected_rows if r.get("destino") == "evaluacion_final"}
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
