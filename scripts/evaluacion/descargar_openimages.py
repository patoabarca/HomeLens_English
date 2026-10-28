from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

try:
    from .evaluacion_common import coco_to_homelens, sha256_file, write_csv
except ImportError:
    from evaluacion_common import coco_to_homelens, sha256_file, write_csv


CANDIDATOS_FIELDS = [
    "open_images_id", "split", "ruta_relativa", "estado_descarga", "width", "height",
    "sha256", "ambiente", "iluminacion", "cantidad_objetos", "categorias", "dificultad",
    "estado_revision", "aceptada", "motivo_descarte", "destino", "autor", "procedencia", "licencia",
]

ANOTACIONES_FIELDS = [
    "open_images_id", "split", "ruta_relativa", "categoria", "confidence",
    "bbox_original_xywh", "bbox_homelens_yxyx", "width", "height",
]


def clases_desde_archivo(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    return [linea.strip() for linea in path.read_text(encoding="utf-8-sig").splitlines() if linea.strip()]


def run_download(args: argparse.Namespace) -> int:
    try:
        import fiftyone as fo
        import fiftyone.zoo as foz
    except ImportError as exc:
        raise SystemExit("FiftyOne no está instalado. Instale requirements-evaluacion.txt en un entorno separado.") from exc

    destino = Path(args.destino).resolve()
    imagenes = destino / "imagenes"
    imagenes.mkdir(parents=True, exist_ok=True)

    clases = clases_desde_archivo(args.classes_file)
    dataset_name = args.dataset_name
    if dataset_name in fo.list_datasets():
        dataset = fo.load_dataset(dataset_name)
    else:
        dataset = foz.load_zoo_dataset(
            "open-images-v7",
            split="validation",
            label_types=["detections"],
            classes=clases,
            max_samples=args.max_samples,
            seed=args.seed,
            shuffle=True,
            only_matching=args.only_matching,
            dataset_name=dataset_name,
        )

    schema = dataset.get_field_schema()
    label_field = "ground_truth" if "ground_truth" in schema else next(
        (name for name, field in schema.items() if getattr(field, "__name__", "") == "Detections"),
        None,
    )

    filas = []
    anotaciones = []
    errores = []
    for sample in dataset:
        source = Path(sample.filepath)
        open_images_id = getattr(sample, "open_images_id", source.stem)
        if source.exists():
            metadata = sample.metadata
            width = getattr(metadata, "width", "") if metadata else ""
            height = getattr(metadata, "height", "") if metadata else ""
            relative = Path(open_images_id).with_suffix(source.suffix)
            destination_file = imagenes / relative.name
            if not destination_file.exists():
                shutil.copy2(source, destination_file)
            if destination_file.exists() and (not width or not height):
                with Image.open(destination_file) as image:
                    width, height = image.size
            state = "descargada" if destination_file.exists() else "fallida"
            detections_container = getattr(sample, label_field, None) if label_field else None
            detections = getattr(detections_container, "detections", []) if detections_container else []
            categorias = sorted({det.label for det in detections if getattr(det, "label", "")})
            for det in detections:
                bbox_relative = getattr(det, "bounding_box", None)
                if bbox_relative is None or not width or not height:
                    continue
                pixel_box = [bbox_relative[0] * int(width), bbox_relative[1] * int(height), bbox_relative[2] * int(width), bbox_relative[3] * int(height)]
                try:
                    bbox_homelens = coco_to_homelens(pixel_box, int(width), int(height))
                except ValueError:
                    errores.append({"open_images_id": str(open_images_id), "error": "bounding box inválido", "bbox": bbox_relative})
                    continue
                anotaciones.append({
                    "open_images_id": str(open_images_id), "split": "validation",
                    "ruta_relativa": str(destination_file.relative_to(destino)).replace("\\", "/"),
                    "categoria": getattr(det, "label", ""), "confidence": getattr(det, "confidence", ""),
                    "bbox_original_xywh": json.dumps([round(value, 8) for value in bbox_relative]),
                    "bbox_homelens_yxyx": json.dumps(bbox_homelens), "width": width, "height": height,
                })
            sha256 = sha256_file(destination_file) if destination_file.exists() else ""
        else:
            width = height = sha256 = ""
            destination_file = imagenes / f"{open_images_id}{source.suffix}"
            state = "fallida"
            categorias = []
            errores.append({"open_images_id": str(open_images_id), "error": "archivo no disponible en FiftyOne", "ruta_fiftyone": str(source)})

        filas.append({
            "open_images_id": str(open_images_id), "split": "validation", "ruta_relativa": str(destination_file.relative_to(destino)).replace("\\", "/"),
            "estado_descarga": state, "width": width, "height": height, "sha256": sha256,
            "ambiente": "pendiente", "iluminacion": "pendiente", "cantidad_objetos": len(categorias),
            "categorias": json.dumps(categorias, ensure_ascii=False), "dificultad": "pendiente",
            "estado_revision": "pendiente", "aceptada": "pendiente", "motivo_descarte": "",
            "destino": "sin asignar", "autor": "pendiente", "procedencia": "Open Images V7", "licencia": "pendiente",
        })

    write_csv(destino / "candidatos.csv", CANDIDATOS_FIELDS, filas)
    write_csv(destino / "anotaciones.csv", ANOTACIONES_FIELDS, anotaciones)
    (destino / "descarga_fallida.json").write_text(json.dumps(errores, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Descarga controlada de imágenes de Open Images V7 para A1")
    parser.add_argument("--max-samples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--classes-file", type=Path)
    parser.add_argument("--destino", type=Path, default=Path("data/evaluacion"))
    parser.add_argument("--dataset-name", default="homelens_a1_validation")
    parser.add_argument("--only-matching", action="store_true", help="Limita imágenes a las categorías indicadas")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_samples < 1:
        raise SystemExit("--max-samples debe ser mayor que cero")
    return run_download(args)


if __name__ == "__main__":
    sys.exit(main())
