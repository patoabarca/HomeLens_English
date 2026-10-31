"""A3: exportar revisión humana, detalle por foto/objeto y resumen general."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from uuid import uuid4

from .dataset_experimento import dentro, guardar_json
from .ejecutar_experimento import RESULTADOS, ahora, registros
from .evaluacion_common import read_csv, sha256_file, write_csv
from .metricas import emparejar, resumir, tiempos

REVISION_CAMPOS = ["run_id", "image_id", "intento", "id_local", "nombre_en", "nombre_es",
                   "frase_en", "frase_es", "identificacion", "referencia_id", "traduccion",
                   "gramatica_en", "pertinencia_en", "gramatica_es", "pertinencia_es", "observaciones"]
CRITERIOS_HUMANOS = ["identificacion", "traduccion", "gramatica_en", "pertinencia_en", "gramatica_es", "pertinencia_es"]


def aplanar(row: dict, prefix: str = "") -> dict:
    flat = {}
    for key, value in row.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(aplanar(value, name))
        else:
            flat[name] = value
    return flat


def tabla(path: Path, rows: list[dict], default: list[str]) -> None:
    flat = [aplanar(row) for row in rows]
    fields = list(dict.fromkeys(key for row in flat for key in row)) or default
    write_csv(path, fields, flat)


def informar(run: Path, revision_path: Path | None = None) -> Path:
    run = dentro(run, RESULTADOS)
    execution = json.loads((run / "ejecucion.json").read_text(encoding="utf-8"))
    for filename in ("metricas.py", "informe_metricas.py"):
        expected = execution["configuracion"]["fuentes_sha256"][f"scripts/evaluacion/{filename}"]
        if sha256_file(Path(__file__).parent / filename) != expected:
            raise ValueError("Los criterios/código de métricas cambiaron desde la ejecución; conservar su versión original")
    latest = registros(run)
    manifest = execution["dataset"]
    annotations = execution["anotaciones"]
    templates = []
    for record in latest:
        if record["estado"] != "valida":
            continue
        for obj in record["respuesta"]["objetos"]:
            templates.append({"run_id": execution["run_id"], "image_id": record["image_id"],
                              "intento": str(record["intento"]), "id_local": obj["id_local"],
                              **{k: obj[k] for k in ("nombre_en", "nombre_es", "frase_en", "frase_es")},
                              **{k: "pendiente" for k in CRITERIOS_HUMANOS},
                              "referencia_id": "", "observaciones": ""})
    review_file = revision_path or run / "revision_humana.csv"
    if not review_file.exists():
        if revision_path:
            raise ValueError("No existe el archivo de revisión indicado")
        write_csv(review_file, REVISION_CAMPOS, templates)
    reviews = read_csv(review_file)
    key = lambda r: (r["image_id"], str(r["intento"]), r["id_local"])
    valid_keys = {key(r) for r in templates}
    review_map = {}
    for review in reviews:
        k = key(review)
        if k not in valid_keys or k in review_map or review["run_id"] != execution["run_id"]:
            raise ValueError("Revisión duplicada o ajena a esta respuesta/ejecución")
        if any(review.get(field) not in {"correcta", "incorrecta", "pendiente"} for field in CRITERIOS_HUMANOS):
            raise ValueError("Usar correcta/incorrecta/pendiente en cada criterio")
        review_map[k] = review
    objects, per_photo, reference_rows = [], [], []
    count_references = 0
    by_image = {r["image_id"]: r for r in latest}
    for image in manifest["imagenes"]:
        record = by_image.get(image["image_id"])
        refs = [{"id": str(r["cvat_annotation_id"]), "categoria": r["categoria"],
                 "box": json.loads(r["bbox_homelens_yxyx"])} for r in annotations if r["image_id"] == image["image_id"]]
        photo = {"image_id": image["image_id"], "origen": image["origen"], "estado": record["estado"] if record else "no_ejecutada",
                 "referencias_cvat": len(refs), "referencias_no_emparejadas": len(refs),
                 "duracion_segundos": record.get("duracion_segundos") if record else None}
        matched = set()
        if record and record["estado"] == "valida":
            predictions = [{**o, "box": [o["recuadro"][k] for k in ("ymin", "xmin", "ymax", "xmax")]} for o in record["respuesta"]["objetos"]]
            photo_reviews = {p["id_local"]: review_map.get((image["image_id"], str(record["intento"]), p["id_local"]), {}) for p in predictions}
            pairs = emparejar(predictions, refs, photo_reviews, image["exhaustiva"])
            photo_objects = []
            for pred, pair in zip(predictions, pairs):
                review = photo_reviews[pred["id_local"]]
                row = {"image_id": image["image_id"], "id_local": pred["id_local"], "intento": record["intento"],
                       **{k: pred[k] for k in ("nombre_en", "nombre_es", "frase_en", "frase_es")},
                       "bbox_predicha_yxyx": json.dumps(pred["box"]), **pair,
                       **{k: review.get(k, "pendiente") for k in CRITERIOS_HUMANOS if k != "identificacion"}}
                photo_objects.append(row)
            matched = {r["referencia_id"] for r in photo_objects if r["referencia_id"]}
            photo["referencias_no_emparejadas"] = len(refs) - len(matched)
            photo["metricas"] = resumir(photo_objects, len(refs))
            count_references += len(refs)
            objects.extend(photo_objects)
        reference_rows.extend({"image_id": image["image_id"], "referencia_id": r["id"], "categoria": r["categoria"],
                               "bbox_cvat_yxyx": json.dumps(r["box"]), "emparejada": r["id"] in matched} for r in refs)
        per_photo.append(photo)
    counts = Counter(r["estado"] for r in latest)
    summary = {"run_id": execution["run_id"], "modo": execution["configuracion"]["modo"],
               "conjunto": manifest["conjunto"], "generado_utc": ahora(),
               "advertencia": "DATOS SIMULADOS: no son resultados de Gemini" if execution["configuracion"]["modo"] == "simulado" else None,
               "fotografias_dataset": len(manifest["imagenes"]), "fotografias_con_intento": len(latest),
               "respuestas_validas": counts["valida"], "fallidas": sum(v for k, v in counts.items() if k not in {"valida", "en_curso"}),
               "en_curso": counts["en_curso"], "no_ejecutadas": len(manifest["imagenes"]) - len(latest),
               "referencias_en_respuestas_validas": count_references,
               "alcance": "Reconocimiento/IoU: respuestas válidas. Cobertura: todas las referencias CVAT de esas fotos. Máximo 5 predicciones/foto. Lingüística: sólo criterios revisados.",
               "metricas": resumir(objects, count_references), "tiempos_ultimo_intento": tiempos(latest),
               "tiempos_todos_intentos": tiempos(registros(run, todos=True))}
    output = dentro(run / "informes" / ("informe_" + uuid4().hex[:12]), run)
    output.mkdir(parents=True, exist_ok=False)
    guardar_json(output / "resumen.json", summary)
    guardar_json(output / "por_fotografia.json", per_photo)
    tabla(output / "resumen.csv", [summary], ["run_id"])
    tabla(output / "por_fotografia.csv", per_photo, ["image_id", "estado"])
    tabla(output / "por_objeto.csv", objects, ["image_id", "id_local"])
    tabla(output / "referencias.csv", reference_rows, ["image_id", "referencia_id"])
    write_csv(output / "revision_aplicada.csv", REVISION_CAMPOS, reviews)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--revision", type=Path)
    args = parser.parse_args()
    try:
        print(informar(args.run, args.revision))
        return 0
    except (ValueError, OSError, KeyError):
        print("No se pudo generar el informe; revisar ejecución y CSV humano.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
