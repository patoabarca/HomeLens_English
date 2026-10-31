from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path


SELECTION_FIELDS = [
    "open_images_id", "ruta_relativa", "ambiente", "iluminacion",
    "dificultad", "estado_revision", "aceptada", "motivo_descarte", "destino",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def image_id(row: dict[str, str]) -> str:
    return (row.get("image_id") or row.get("open_images_id") or "").strip()


def homelens_box_to_css(box: list[object]) -> dict[str, float]:
    if len(box) != 4:
        raise ValueError("El bounding box HomeLens debe tener cuatro valores")
    ymin, xmin, ymax, xmax = [float(value) for value in box]
    if any(value < 0 or value > 1000 for value in (ymin, xmin, ymax, xmax)):
        raise ValueError("El bounding box HomeLens queda fuera de rango")
    if ymin >= ymax or xmin >= xmax:
        raise ValueError("El bounding box HomeLens debe tener area positiva")
    return {
        "left": xmin / 10,
        "top": ymin / 10,
        "width": (xmax - xmin) / 10,
        "height": (ymax - ymin) / 10,
    }


def generate(root: Path, output: Path) -> Path:
    candidates = read_csv(root / "candidatos.csv")
    annotations = defaultdict(list)
    annotations_path = root / "anotaciones.csv"
    if annotations_path.exists():
        for row in read_csv(annotations_path):
            try:
                box = json.loads(row.get("bbox_homelens_yxyx", "[]"))
                css_box = homelens_box_to_css(box)
            except json.JSONDecodeError:
                continue
            except (TypeError, ValueError):
                continue
            annotations[image_id(row)].append({
                "box": css_box,
                "label": row["categoria"],
            })

    candidates.sort(
        key=lambda row: int(row.get("puntaje_domestico", "0") or 0),
        reverse=True,
    )
    cards = []
    for row in candidates:
        image_rel = row.get("ruta_relativa", "").replace("\\", "/")
        if not image_rel and row.get("nombre_archivo"):
            image_rel = "../../fotografias_originales/{}/{}".format(
                row.get("lote", "").replace("\\", "/").strip("/"),
                row["nombre_archivo"].replace("\\", "/"),
            )
        identifier = image_id(row)
        boxes = annotations[identifier]
        box_html = []
        for item in boxes:
            box = item["box"]
            box_html.append(
                '<span class="box" style="left:{:.4%};top:{:.4%};width:{:.4%};height:{:.4%}">'
                '<b>{}</b></span>'.format(
                    box["left"] / 100,
                    box["top"] / 100,
                    box["width"] / 100,
                    box["height"] / 100,
                    html.escape(item["label"]),
                )
            )
        accepted = row.get("aceptada", "pendiente").strip().lower()
        if accepted == "si":
            accepted_options = (
                '<option value="pendiente">Pendiente de revisar</option>'
                '<option value="si" selected>Sí</option><option value="no">No</option>'
            )
        elif accepted == "no":
            accepted_options = (
                '<option value="pendiente">Pendiente de revisar</option>'
                '<option value="si">Sí</option><option value="no" selected>No</option>'
            )
        else:
            accepted_options = (
                '<option value="pendiente" selected>Pendiente de revisar</option>'
                '<option value="si">Sí</option><option value="no">No</option>'
            )
        observations = html.escape(
            row.get("observaciones", "") or row.get("motivo_descarte", ""),
        )
        cards.append(
            '<article class="card" data-id="{id}">'
            '<span class="legacy-meta" hidden data-open-images-id="{oi}" data-ruta-relativa="{ruta}" '
            'data-ambiente="{ambiente}" data-iluminacion="{iluminacion}" data-dificultad="{dificultad}" '
            'data-motivo-descarte="{motivo}" data-destino="{destino}" data-estado-revision="{estado}"></span>'
            '<div class="image-wrap"><img src="{src}" alt="{id}">{boxes}</div>'
            '<div class="meta"><strong>{id}</strong></div>'
            '<label>¿Anotaciones correctas?<select class="aceptada">'
            '{accepted_options}</select></label>'
            '<label>Observaciones<textarea class="observaciones" rows="3" placeholder="Observaciones opcionales">{observations}</textarea></label>'
            '</article>'.format(
                id=html.escape(identifier),
                src=html.escape(image_rel, quote=True),
                boxes="".join(box_html),
                accepted_options=accepted_options,
                observations=observations,
                oi=html.escape(row.get("open_images_id", ""), quote=True),
                ruta=html.escape(row.get("ruta_relativa", ""), quote=True),
                ambiente=html.escape(row.get("ambiente", ""), quote=True),
                iluminacion=html.escape(row.get("iluminacion", ""), quote=True),
                dificultad=html.escape(row.get("dificultad", ""), quote=True),
                motivo=html.escape(row.get("motivo_descarte", ""), quote=True),
                destino=html.escape(row.get("destino", ""), quote=True),
                estado=html.escape(row.get("estado_revision", ""), quote=True),
            )
        )

    page = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Revisión visual A1</title>
<style>
body{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}.card{background:white;border-radius:8px;padding:12px;box-shadow:0 1px 4px #bbb}.image-wrap{position:relative;display:block;width:100%;line-height:0;overflow:hidden}.image-wrap img{display:block;width:100%;height:auto;max-height:none}.box{position:absolute;border:2px solid #ff3b30;pointer-events:none;line-height:normal;box-sizing:border-box}.box b{font-size:10px;background:#ff3b30;color:white;padding:1px 3px}.meta{display:flex;flex-wrap:wrap;gap:8px;padding:8px 0}.card label{display:grid;grid-template-columns:150px 1fr;margin:4px 0}input,select,textarea{padding:5px;font-family:Arial,sans-serif}textarea{resize:vertical}button{position:sticky;top:8px;margin:0 0 16px;padding:10px 16px;font-size:16px}
</style></head><body><h1>Revisión visual A1</h1>
<button onclick="downloadReview()">Descargar decisiones CSV</button><div class="grid">""" + "".join(cards) + """</div>
<script>
function downloadReview(){
 const rows=[["image_id","open_images_id","ruta_relativa","aceptada","observaciones","ambiente","iluminacion","dificultad","motivo_descarte","destino","estado_revision"]];
 document.querySelectorAll(".card").forEach(card=>{
  const legacy=card.querySelector(".legacy-meta");
  const accepted=card.querySelector(".aceptada")?.value||"pendiente";
  const observations=card.querySelector(".observaciones")?.value||"";
  const get=key=>legacy?.dataset[key]||"";
  rows.push([
   card.dataset.id,get("openImagesId"),get("rutaRelativa"),accepted,observations,
   get("ambiente"),get("iluminacion"),get("dificultad"),
   observations && accepted==="no" ? observations : get("motivoDescarte"),
   get("destino"),accepted==="pendiente"?"pendiente":"revisada"
  ]);
 });
 const csv=rows.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(",")).join("\\n");
 const blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
 const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="seleccion_revision.csv";a.click();
}
</script></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera una galería HTML de revisión visual A1")
    parser.add_argument("--root", type=Path, default=Path("data/evaluacion"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve() if args.output else root / "revision_visual.html"
    generated = generate(root, output)
    print(generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
