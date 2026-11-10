from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter
from pathlib import Path
from zipfile import ZipFile, BadZipFile
import os

from PIL import Image

try:
    from .evaluacion_common import coco_to_homelens, sha256_file, write_csv
except ImportError:
    from evaluacion_common import coco_to_homelens, sha256_file, write_csv


COCO_PATH = "annotations/instances_default.json"


def aspect_ratio(width: int, height: int) -> float:
    return width / height if height else 0.0


def find_coco_file(export_zip: Path) -> str:
    with ZipFile(export_zip, "r") as archive:
        names = set(archive.namelist())
    candidates = [name for name in names if name.endswith("instances_default.json")]
    if not candidates:
        raise ValueError("No se encontró annotations/instances_default.json en el ZIP")
    if len(candidates) > 1:
        raise ValueError("El ZIP contiene más de una exportación COCO 1.0")
    return candidates[0]


def find_original_photo(directory: Path, declared_name: str) -> Path | None:
    if not directory.is_dir():
        return None
    exact = directory / Path(declared_name).name
    if exact.is_file():
        return exact

    declared = Path(declared_name).name
    for candidate in directory.iterdir():
        if not candidate.is_file():
            continue
        candidate_name = candidate.name
        for suffix in (".jpeg", ".jpg", ".png", ".webp"):
            if candidate_name.lower().endswith(suffix):
                candidate_base = candidate_name
                break
        variants = {
            candidate_name,
            candidate_name.removesuffix(".jpeg").removesuffix(".JPEG"),
            candidate_name.removesuffix(".jpg").removesuffix(".JPG"),
            candidate_name.removesuffix(".png").removesuffix(".PNG"),
            candidate_name.removesuffix(".webp").removesuffix(".WEBP"),
        }
        if declared in variants:
            return candidate
    return None


def import_cvat(
    export_zip: Path,
    output: Path,
    lote: str = "piloto",
    destino: str = "piloto",
    fotografias_originales: Path | None = None,
    revision_csv: Path | None = None,
) -> dict:
    export_zip = export_zip.resolve()
    output = output.resolve()
    if not export_zip.is_file():
        raise FileNotFoundError(export_zip)

    try:
        if export_zip.suffix.lower() == ".json":
            coco = json.loads(export_zip.read_text(encoding="utf-8-sig"))
        else:
            coco_path = find_coco_file(export_zip)
            with ZipFile(export_zip, "r") as archive:
                coco = json.loads(archive.read(coco_path).decode("utf-8-sig"))
    except BadZipFile as exc:
        raise ValueError("El archivo no es un ZIP válido") from exc

    images = coco.get("images")
    categories = coco.get("categories")
    annotations = coco.get("annotations")
    if not isinstance(images, list) or not isinstance(categories, list) or not isinstance(annotations, list):
        raise ValueError("El archivo COCO debe contener arrays images, categories y annotations")

    category_ids = {category["id"]: category["name"] for category in categories}
    image_by_id = {image["id"]: image for image in images}
    if len(category_ids) != len(categories):
        raise ValueError("Hay identificadores de categoría duplicados")
    if len(image_by_id) != len(images):
        raise ValueError("Hay identificadores de fotografía duplicados en COCO")
    filenames = [image.get("file_name") for image in images]
    if any(not isinstance(name, str) or not name for name in filenames) or len(set(filenames)) != len(filenames):
        raise ValueError("Los nombres de archivo COCO deben ser únicos y no vacíos")
    annotation_ids = [annotation.get("id") for annotation in annotations]
    try:
        unique_annotation_ids = len(set(annotation_ids)) == len(annotation_ids)
    except TypeError:
        unique_annotation_ids = False
    if any(value is None or value == "" for value in annotation_ids) or not unique_annotation_ids:
        raise ValueError("Los identificadores de anotación deben ser únicos y no vacíos")

    normalized_annotations = []
    annotation_counts = Counter()
    used_categories = Counter()
    for annotation in annotations:
        image_id = annotation.get("image_id")
        category_id = annotation.get("category_id")
        if image_id not in image_by_id:
            raise ValueError(f"La anotación referencia una imagen inexistente: {image_id}")
        if category_id not in category_ids:
            raise ValueError(f"La anotación referencia una categoría inexistente: {category_id}")
        image = image_by_id[image_id]
        width, height = image.get("width"), image.get("height")
        if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
            raise ValueError(f"Dimensiones inválidas para la fotografía {image_id}")
        box = annotation.get("bbox")
        if (
            not isinstance(box, list)
            or len(box) != 4
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in box)
        ):
            raise ValueError(f"Bounding box inválido para la anotación {annotation.get('id')}")
        home_box = coco_to_homelens(box, width, height)
        xmin, ymin, box_width, box_height = [float(value) for value in box]
        normalized_original = [
            xmin / width,
            ymin / height,
            box_width / width,
            box_height / height,
        ]
        normalized_annotations.append({
            "image_id": f"cvat_{lote}_{image_id}",
            "cvat_image_id": image_id,
            "categoria": category_ids[category_id],
            "cvat_category_id": category_id,
            "bbox_homelens_yxyx": json.dumps(home_box, separators=(",", ":")),
            "bbox_original_xywh": json.dumps(normalized_original, separators=(",", ":")),
            "segmentation": json.dumps(annotation.get("segmentation", []), ensure_ascii=False),
            "is_crowd": annotation.get("iscrowd", 0),
            "cvat_annotation_id": annotation.get("id"),
        })
        annotation_counts[image_id] += 1
        used_categories[category_ids[category_id]] += 1

    output.mkdir(parents=True, exist_ok=True)
    if export_zip.suffix.lower() != ".json":
        export_dir = output / "exportaciones"
        export_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(export_zip, export_dir / export_zip.name)

    if fotografias_originales is None:
        fotografias_originales = output.parents[1] / "fotografias_originales" / lote
    else:
        fotografias_originales = fotografias_originales.resolve()

    candidates = []
    normalized_images = []
    previous_normalized = {}
    previous_normalized_path = output / "imagenes_normalizadas.json"
    if previous_normalized_path.is_file():
        try:
            previous_normalized = {
                item["file_name"]: item
                for item in json.loads(previous_normalized_path.read_text(encoding="utf-8"))
                if isinstance(item, dict) and item.get("file_name")
            }
        except json.JSONDecodeError:
            previous_normalized = {}
    previous_candidates = {}
    previous_candidates_path = output / "candidatos.csv"
    if previous_candidates_path.is_file():
        import csv
        with previous_candidates_path.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                previous_candidates[row.get("image_id", "")] = row
    review_rows = {}
    if revision_csv is not None and revision_csv.is_file():
        with revision_csv.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                review_rows[row.get("image_id", "")] = row
    else:
        automatic_review = output / "seleccion_revision.csv"
        if automatic_review.is_file():
            with automatic_review.open("r", newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    review_rows[row.get("image_id", "")] = row

    for image in images:
        image_id = f"cvat_{lote}_{image['id']}"
        original_path = find_original_photo(fotografias_originales, image["file_name"])
        route_relative = ""
        download_state = "pendiente_fotografia_original"
        image_hash = ""
        actual_width = None
        actual_height = None
        actual_format = None
        if original_path is not None and original_path.is_file():
            route_relative = os.path.relpath(original_path, output).replace("\\", "/")
            image_hash = sha256_file(original_path)
            download_state = "fotografia_original_disponible"
            try:
                with Image.open(original_path) as photo:
                    actual_width, actual_height = photo.size
                    actual_format = photo.format
                if (actual_width, actual_height) != (int(image["width"]), int(image["height"])):
                    download_state = "fotografia_original_discrepancia_dimensiones"
                    previous_image = previous_normalized.get(image["file_name"], {})
                    transformation = previous_image.get("transformacion_validada")
                    if isinstance(transformation, dict):
                        ratio_difference = abs(
                            (actual_width / actual_height)
                            - (int(image["width"]) / int(image["height"]))
                        )
                        if (
                            transformation.get("method") == "uniform_resize_same_aspect_ratio"
                            and transformation.get("visual_review_accepted") is True
                            and transformation.get("coco_width") == int(image["width"])
                            and transformation.get("coco_height") == int(image["height"])
                            and transformation.get("actual_width") == actual_width
                            and transformation.get("actual_height") == actual_height
                            and 0 <= ratio_difference <= 0.001
                        ):
                            download_state = "fotografia_original_transformacion_validada"
            except Exception:
                download_state = "fotografia_original_ilegible"
        candidate = {
            "image_id": image_id,
            "open_images_id": "",
            "fuente": "CVAT",
            "lote": lote,
            "destino": destino,
            "nombre_archivo": image["file_name"],
            "ruta_relativa": route_relative,
            "estado_descarga": download_state,
            "cantidad_objetos": annotation_counts[image["id"]],
            "categorias": json.dumps(sorted({
                category_ids[a["category_id"]] for a in annotations if a["image_id"] == image["id"]
            }), ensure_ascii=False),
            "aceptada": "pendiente",
            "estado_revision": "pendiente",
            "motivo_descarte": "",
            "ambiente": "pendiente",
            "sha256": image_hash,
        }
        previous = previous_candidates.get(image_id, {})
        review = review_rows.get(image_id, {})
        for field in (
            "observaciones", "estado_revision", "iluminacion", "dificultad",
            "motivo_descarte", "ambiente", "destino", "aceptada",
            "ruta_relativa", "sha256", "open_images_id",
        ):
            if review:
                candidate[field] = review.get(field, candidate.get(field, previous.get(field, "")))
            elif previous:
                candidate[field] = previous.get(field, candidate.get(field, ""))
        candidates.append(candidate)
        normalized_images.append({
            "image_id": image_id,
            "cvat_image_id": image["id"],
            "file_name": image["file_name"],
            "width": image["width"],
            "height": image["height"],
            "actual_width": actual_width,
            "actual_height": actual_height,
            "actual_format": actual_format,
            "coco_url": image.get("coco_url", ""),
            "flickr_url": image.get("flickr_url", ""),
            "date_captured": image.get("date_captured", 0),
            "transformacion_validada": previous_normalized.get(
                image["file_name"], {}
            ).get("transformacion_validada"),
        })

    candidate_fields = [
        "image_id", "open_images_id", "fuente", "lote", "destino", "nombre_archivo",
        "ruta_relativa", "estado_descarga", "cantidad_objetos", "categorias",
        "aceptada", "motivo_descarte", "ambiente", "sha256",
        "observaciones", "estado_revision", "iluminacion", "dificultad",
    ]
    write_csv(output / "candidatos.csv", candidate_fields, candidates)
    write_csv(
        output / "anotaciones.csv",
        ["image_id", "cvat_image_id", "categoria", "cvat_category_id",
         "bbox_homelens_yxyx", "bbox_original_xywh", "segmentation", "is_crowd",
         "cvat_annotation_id"],
        normalized_annotations,
    )
    (output / "imagenes_normalizadas.json").write_text(
        json.dumps(normalized_images, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "categorias.json").write_text(
        json.dumps([
            {"id": category["id"], "name": category["name"], "supercategory": category.get("supercategory", "")}
            for category in categories
        ], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    provenance = {
        "fuente": "CVAT",
        "formato": "COCO 1.0",
        "origen_exportacion": export_zip.name,
        "export_sha256": sha256_file(export_zip),
        "lote": lote,
        "destino": destino,
        "fotografias_originales": "pendiente",
        "permisos": "pendiente de documentación",
    }
    provenance_path = output / "procedencia.json"
    if provenance_path.is_file():
        try:
            previous_provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            if isinstance(previous_provenance.get("revision_humana"), dict):
                provenance["revision_humana"] = previous_provenance["revision_humana"]
            if previous_provenance.get("fotografias_originales") not in (None, "", "pendiente"):
                provenance["fotografias_originales"] = previous_provenance["fotografias_originales"]
            if previous_provenance.get("permisos") not in (None, "", "pendiente de documentación"):
                provenance["permisos"] = previous_provenance["permisos"]
        except json.JSONDecodeError:
            pass
    (output / "procedencia.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "valid": True,
        "counts": {
            "imagenes": len(images),
            "anotaciones": len(annotations),
            "categorias_utilizadas": len(used_categories),
            "recuadros": len(normalized_annotations),
        },
        "output": str(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa exportaciones CVAT COCO 1.0 a metadatos HomeLens")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--export-zip", type=Path)
    source.add_argument("--coco-json", type=Path, help="Archivo COCO JSON extraído de una exportación")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lote", default="piloto")
    parser.add_argument("--destino", choices=["piloto", "evaluacion_final", "pendiente"], default="piloto")
    parser.add_argument(
        "--fotografias-originales",
        type=Path,
        help="Directorio del lote con las fotografías originales; por defecto se infiere junto al lote CVAT",
    )
    parser.add_argument(
        "--revision-csv",
        type=Path,
        help="CSV exportado por la galería; conserva las decisiones humanas en una reimportación",
    )
    args = parser.parse_args()
    try:
        result = import_cvat(
            args.export_zip or args.coco_json,
            args.output,
            args.lote,
            args.destino,
            args.fotografias_originales,
            args.revision_csv,
        )
    except (FileNotFoundError, ValueError, BadZipFile) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
