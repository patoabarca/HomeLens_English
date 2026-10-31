"""A3: correspondencia conservadora uno a uno y métricas con denominadores."""
from __future__ import annotations

import math
import statistics
import unicodedata
from collections import Counter

VERSION_CRITERIOS = "a3-v1"
SINONIMOS = {
    "sofa": ["sofa", "couch", "settee"],
    "television": ["television", "tv", "television set"],
    "refrigerator": ["refrigerator", "fridge"],
    "cabinet": ["cabinet", "cupboard"],
    "drapes": ["drapes", "curtain", "curtains"],
    "rug": ["rug", "carpet"],
    "lamp": ["lamp", "light fixture"],
    "chair": ["chair", "chairs"],
    "picture": ["picture", "painting", "framed picture"],
    "plant": ["plant", "potted plant", "houseplant"],
    "cushion": ["cushion", "throw pillow"],
}


def normalizar(text: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)).split())


def categoria(text: str) -> str:
    text = normalizar(text)
    return next((key for key, values in SINONIMOS.items() if text in values), text)


def validar_box(box: list) -> list:
    if len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1000 for v in box):
        raise ValueError("Recuadro inválido: usar [ymin,xmin,ymax,xmax] en [0,1000]")
    y1, x1, y2, x2 = box
    if y1 >= y2 or x1 >= x2:
        raise ValueError("El recuadro debe tener área positiva")
    return box


def iou(a: list, b: list) -> float:
    ay1, ax1, ay2, ax2 = validar_box(a)
    by1, bx1, by2, bx2 = validar_box(b)
    inter = max(0, min(ay2, by2) - max(ay1, by1)) * max(0, min(ax2, bx2) - max(ax1, bx1))
    return inter / ((ay2 - ay1) * (ax2 - ax1) + (by2 - by1) * (bx2 - bx1) - inter)


def proporcion(n: int, d: int) -> dict:
    return {"numerador": n, "denominador": d, "valor": n / d if d else None}


def emparejar(pred: list[dict], refs: list[dict], revisiones: dict, exhaustiva: bool) -> list[dict]:
    """Asignación exacta O(referencias * 2^predicciones * predicciones), máximo 5.

    Maximiza primero cantidad y luego IoU total. Las categorías repetidas sin
    superposición o con igual evidencia geométrica requieren revisión humana.
    Una revisión puede confirmar presencia sin inventar una referencia CVAT.
    """
    if len(pred) > 5:
        raise ValueError("Máximo cinco detecciones")
    refmap = {str(r["id"]): r for r in refs}
    if len(refmap) != len(refs):
        raise ValueError("IDs de referencia repetidos")
    used, results, pending = set(), {}, []
    for index, obj in enumerate(pred):
        review = revisiones.get(obj["id_local"], {})
        state = review.get("identificacion", "pendiente")
        if state not in {"correcta", "incorrecta", "pendiente"}:
            raise ValueError("Revisión de identificación inválida")
        rid = review.get("referencia_id", "")
        if rid and state != "correcta":
            raise ValueError("Una referencia manual exige identificación correcta")
        if rid:
            if rid not in refmap or rid in used:
                raise ValueError("Referencia manual inexistente o reutilizada")
            used.add(rid)
        if state != "pendiente":
            results[index] = {"identificacion": state, "referencia_id": rid, "criterio": "humano"}
        else:
            pending.append(index)
    available = [r for r in refs if str(r["id"]) not in used]
    counts = Counter(categoria(r["categoria"]) for r in refs)
    edges, ambiguous = {}, set()
    for index in pending:
        obj = pred[index]
        candidates = [(str(r["id"]), iou(obj["box"], r["box"])) for r in available if categoria(obj["nombre_en"]) == categoria(r["categoria"])]
        # Empates entre instancias repetidas se mantienen pendientes.
        tied = len(candidates) > 1 and sum(abs(v - max(x[1] for x in candidates)) < 1e-12 for _, v in candidates) > 1
        if tied or (counts[categoria(obj["nombre_en"])] > 1 and not any(v > 0 for _, v in candidates)):
            ambiguous.add(index)
        edges[index] = {} if tied else {rid: v for rid, v in candidates if counts[categoria(obj["nombre_en"])] == 1 or v > 0}
    dp = {0: (0.0, {})}
    for ref in available:
        rid = str(ref["id"])
        new = dict(dp)
        for mask, (score, pairs) in dp.items():
            for index in pending:
                if mask & (1 << index) or rid not in edges[index]:
                    continue
                key = mask | (1 << index)
                value = score + edges[index][rid]
                if key not in new or value > new[key][0]:
                    new[key] = (value, {**pairs, index: rid})
        dp = new
    best = max(dp, key=lambda mask: (mask.bit_count(), dp[mask][0]))
    for index, rid in dp[best][1].items():
        results[index] = {"identificacion": "correcta", "referencia_id": rid, "criterio": "equivalencia_uno_a_uno"}
    # Dos predicciones indistinguibles que compiten por la misma instancia son ambiguas.
    for index, result in list(results.items()):
        if result["criterio"] != "equivalencia_uno_a_uno":
            continue
        rid = result["referencia_id"]
        if any(j != index and rid in edges[j] and abs(edges[j][rid] - edges[index][rid]) < 1e-12 for j in pending):
            del results[index]
    for index, obj in enumerate(pred):
        result = results.setdefault(index, {"identificacion": "incorrecta" if exhaustiva and index not in ambiguous and not edges.get(index) else "pendiente", "referencia_id": "", "criterio": "sin_correspondencia"})
        rid = result["referencia_id"]
        result.update({"id_local": obj["id_local"], "iou": iou(obj["box"], refmap[rid]["box"]) if rid else None})
    return [results[i] for i in range(len(pred))]


def revision_porcentaje(rows: list[dict], field: str) -> dict:
    states = [r.get(field, "pendiente") for r in rows]
    if any(s not in {"correcta", "incorrecta", "pendiente"} for s in states):
        raise ValueError("Usar correcta/incorrecta/pendiente en la revisión humana")
    return {**proporcion(states.count("correcta"), sum(s != "pendiente" for s in states)), "pendientes": states.count("pendiente")}


def tiempos(records: list[dict]) -> dict:
    result = {}
    for label, success in (("exitosas", True), ("fallidas", False)):
        values = [r["duracion_segundos"] for r in records if (r["estado"] == "valida") == success and r.get("duracion_segundos") is not None]
        result[label] = {"cantidad": len(values), "promedio": statistics.mean(values) if values else None,
                         "mediana": statistics.median(values) if values else None,
                         "minimo": min(values) if values else None, "maximo": max(values) if values else None}
    return result


def resumir(objects: list[dict], referencias: int) -> dict:
    correct = sum(r["identificacion"] == "correcta" for r in objects)
    wrong = sum(r["identificacion"] == "incorrecta" for r in objects)
    values = [r["iou"] for r in objects if r["iou"] is not None]
    localized = sum(v >= 0.5 for v in values)
    return {"detecciones": len(objects), "pendientes_identificacion": len(objects) - correct - wrong,
            "precision_revisadas": proporcion(correct, correct + wrong),
            "fraccion_confirmada_total": proporcion(correct, len(objects)),
            "cobertura_referencias": proporcion(len(values), referencias),
            "iou": {"promedio": statistics.mean(values) if values else None, "emparejados": len(values), "suma": sum(values), "al_menos_050": localized},
            "deteccion_localizacion_revisadas": proporcion(localized, correct + wrong),
            "sin_emparejar": len(objects) - len(values),
            **{field: revision_porcentaje(objects, field) for field in ("traduccion", "gramatica_en", "pertinencia_en", "gramatica_es", "pertinencia_es")}}
