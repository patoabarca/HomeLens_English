from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

try:
    from .evaluacion_common import read_csv, write_csv
except ImportError:
    from evaluacion_common import read_csv, write_csv


DECISION_FIELDS = [
    "image_id",
    "open_images_id",
    "ruta_relativa",
    "aceptada",
    "observaciones",
    "ambiente",
    "iluminacion",
    "dificultad",
    "motivo_descarte",
    "destino",
    "estado_revision",
]


def importar_revision(root: Path, revision_csv: Path) -> dict:
    root = root.resolve()
    revision_csv = revision_csv.resolve()
    candidates_path = root / "candidatos.csv"
    if not candidates_path.is_file():
        raise FileNotFoundError(candidates_path)
    if not revision_csv.is_file():
        raise FileNotFoundError(revision_csv)

    candidates = read_csv(candidates_path)
    decisions = read_csv(revision_csv)
    candidates_by_id = {}
    for candidate in candidates:
        image_id = (candidate.get("image_id") or candidate.get("open_images_id") or "").strip()
        if not image_id:
            raise ValueError("Existe una candidatura sin image_id")
        if image_id in candidates_by_id:
            raise ValueError(f"Identificador de candidatura duplicado: {image_id}")
        candidates_by_id[image_id] = candidate

    decisions_by_id = {}
    for decision in decisions:
        image_id = (decision.get("image_id") or decision.get("open_images_id") or "").strip()
        if not image_id:
            raise ValueError("Existe una decisión sin image_id")
        if image_id in decisions_by_id:
            raise ValueError(f"Identificador de decisión duplicado: {image_id}")
        if image_id not in candidates_by_id:
            raise ValueError(f"La decisión referencia una imagen inexistente: {image_id}")
        accepted = decision.get("aceptada", "").strip().lower()
        if accepted not in {"si", "no", "pendiente"}:
            raise ValueError(f"Decisión inválida para {image_id}: {accepted or '<vacía>'}")
        decisions_by_id[image_id] = decision

    unknown_fields = [
        field for field in decisions[0].keys()
        if field and field not in DECISION_FIELDS and field not in candidates_by_id
    ] if decisions else []

    for image_id, decision in decisions_by_id.items():
        candidate = candidates_by_id[image_id]
        accepted = decision.get("aceptada", "").strip().lower()
        observations = decision.get("observaciones", "").strip()
        candidate["aceptada"] = accepted
        candidate["observaciones"] = observations
        candidate["estado_revision"] = decision.get("estado_revision", "").strip() or (
            "pendiente" if accepted == "pendiente" else "revisada"
        )
        candidate["motivo_descarte"] = decision.get("motivo_descarte", "").strip()
        candidate["ambiente"] = decision.get("ambiente", candidate.get("ambiente", "")).strip()
        candidate["iluminacion"] = decision.get("iluminacion", "").strip() or candidate.get("iluminacion", "")
        candidate["dificultad"] = decision.get("dificultad", "").strip() or candidate.get("dificultad", "")
        candidate["destino"] = decision.get("destino", "").strip() or candidate.get("destino", "")
        candidate["open_images_id"] = decision.get("open_images_id", candidate.get("open_images_id", "")).strip()
        candidate["ruta_relativa"] = decision.get("ruta_relativa", candidate.get("ruta_relativa", "")).strip()

    candidate_fields = list(candidates[0].keys()) if candidates else list(DECISION_FIELDS)
    for field in (
        "observaciones", "estado_revision", "iluminacion", "dificultad",
        "motivo_descarte", "ambiente", "destino", "aceptada", "ruta_relativa",
        "open_images_id",
    ):
        if field not in candidate_fields:
            candidate_fields.append(field)
    write_csv(candidates_path, candidate_fields, candidates)

    selection_rows = []
    for candidate in candidates:
        image_id = (candidate.get("image_id") or candidate.get("open_images_id") or "").strip()
        if image_id in decisions_by_id:
            selection_rows.append({
                "image_id": image_id,
                "open_images_id": candidate.get("open_images_id", ""),
                "ruta_relativa": candidate.get("ruta_relativa", ""),
                "ambiente": candidate.get("ambiente", ""),
                "iluminacion": candidate.get("iluminacion", ""),
                "dificultad": candidate.get("dificultad", ""),
                "estado_revision": candidate.get("estado_revision", ""),
                "aceptada": candidate.get("aceptada", ""),
                "motivo_descarte": candidate.get("motivo_descarte", ""),
                "destino": candidate.get("destino", ""),
                "observaciones": candidate.get("observaciones", ""),
            })
    selection_fields = [
        "image_id", "open_images_id", "ruta_relativa", "ambiente",
        "iluminacion", "dificultad", "estado_revision", "aceptada",
        "motivo_descarte", "destino", "observaciones",
    ]
    write_csv(root / "seleccion.csv", selection_fields, selection_rows)

    provenance_path = root / "procedencia.json"
    provenance = {}
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["revision_humana"] = {
        "archivo_decisiones": revision_csv.name,
        "cantidad_decisiones": len(decisions_by_id),
        "cantidad_aceptadas": sum(
            1 for decision in decisions_by_id.values()
            if decision.get("aceptada", "").strip().lower() == "si"
        ),
        "estado": "completada" if len(decisions_by_id) == len(candidates) else "parcial",
    }
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "valid": True,
        "decisiones": len(decisions_by_id),
        "aceptadas": sum(1 for decision in decisions_by_id.values() if decision.get("aceptada", "").strip().lower() == "si"),
        "rechazadas": sum(1 for decision in decisions_by_id.values() if decision.get("aceptada", "").strip().lower() == "no"),
        "candidaturas_actualizadas": len(candidates),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Incorpora decisiones humanas exportadas desde la galería A1")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--revision-csv", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = importar_revision(args.root, args.revision_csv)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (FileNotFoundError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
