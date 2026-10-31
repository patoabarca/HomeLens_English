import csv
import json
import zipfile
from pathlib import Path

from PIL import Image

from scripts.evaluacion.evaluacion_common import coco_to_homelens, read_csv, sha256_file, write_csv
from scripts.evaluacion.validar_dataset import validate
from scripts.evaluacion.importar_cvat import import_cvat
from scripts.evaluacion.importar_revision import importar_revision
from scripts.evaluacion.generar_galeria_revision import generate, homelens_box_to_css


def test_coco_to_homelens_keeps_axis_order():
    assert coco_to_homelens([100, 50, 200, 100], 400, 200) == [250, 250, 750, 750]


def test_coco_to_homelens_rejects_invalid_box():
    try:
        coco_to_homelens([350, 50, 100, 100], 400, 200)
        assert False, "Debería rechazar el recuadro fuera de rango"
    except ValueError:
        pass


def test_read_csv_and_sha256(tmp_path: Path):
    image = tmp_path / "test.png"
    Image.new("RGB", (40, 20), "white").save(image)
    csv_path = tmp_path / "candidatos.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "hash"])
        writer.writeheader()
        writer.writerow({"id": "1", "hash": sha256_file(image)})
    assert read_csv(csv_path)[0]["id"] == "1"


def test_validator_accepts_valid_candidate(tmp_path: Path):
    image_dir = tmp_path / "imagenes"
    image_dir.mkdir()
    image = image_dir / "one.jpg"
    Image.new("RGB", (40, 20), "white").save(image, format="JPEG")
    digest = sha256_file(image)
    with (tmp_path / "candidatos.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["open_images_id", "ruta_relativa", "estado_descarga", "sha256"])
        writer.writeheader()
        writer.writerow({"open_images_id": "one", "ruta_relativa": "imagenes/one.jpg", "estado_descarga": "descargada", "sha256": digest})
    result = validate(tmp_path)
    assert result["valid"]
    assert result["counts"]["candidatas"] == 1


def test_validator_rejects_missing_downloaded_file(tmp_path: Path):
    with (tmp_path / "candidatos.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["open_images_id", "ruta_relativa", "estado_descarga", "sha256"])
        writer.writeheader()
        writer.writerow({"open_images_id": "missing", "ruta_relativa": "imagenes/missing.jpg", "estado_descarga": "descargada", "sha256": "x"})
    result = validate(tmp_path)
    assert not result["valid"]


def test_validator_rejects_mismatched_object_count(tmp_path: Path):
    image_dir = tmp_path / "imagenes"
    image_dir.mkdir()
    image = image_dir / "one.jpg"
    Image.new("RGB", (40, 20), "white").save(image, format="JPEG")
    digest = sha256_file(image)
    with (tmp_path / "candidatos.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["open_images_id", "ruta_relativa", "estado_descarga", "sha256", "cantidad_objetos"])
        writer.writeheader()
        writer.writerow({"open_images_id": "one", "ruta_relativa": "imagenes/one.jpg", "estado_descarga": "descargada", "sha256": digest, "cantidad_objetos": "1"})
    with (tmp_path / "anotaciones.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["open_images_id", "categoria", "bbox_homelens_yxyx"])
        writer.writeheader()
        writer.writerow({"open_images_id": "one", "categoria": "Chair", "bbox_homelens_yxyx": "[100,100,800,800]"})
        writer.writerow({"open_images_id": "one", "categoria": "Table", "bbox_homelens_yxyx": "[100,100,900,900]"})
    result = validate(tmp_path)
    assert not result["valid"]
    assert any("cantidad_objetos" in error for error in result["errors"])


def test_domestic_class_list_excludes_natural_categories():
    class_list = Path("scripts/evaluacion/clases_domesticas.txt").read_text(encoding="utf-8-sig").splitlines()
    assert "Plant" not in class_list
    assert "Tree" not in class_list
    assert "Refrigerator" in class_list
    assert "Computer monitor" in class_list


def make_cvat_zip(path: Path, image_count: int = 5, annotation_count: int = 26):
    images = [
        {"id": index + 1, "width": 1000, "height": 800, "file_name": f"image_{index + 1}.jpg"}
        for index in range(image_count)
    ]
    categories = [
        {"id": 1, "name": "Chair", "supercategory": ""},
        {"id": 2, "name": "Table", "supercategory": ""},
    ]
    annotations = []
    for index in range(annotation_count):
        annotations.append({
            "id": index + 1,
            "image_id": (index % image_count) + 1,
            "category_id": 1 if index % 2 == 0 else 2,
            "bbox": [10 + index, 20 + index, 100, 80],
            "iscrowd": 0,
            "segmentation": [],
        })
    coco = {
        "images": images,
        "categories": categories,
        "annotations": annotations,
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("annotations/instances_default.json", json.dumps(coco))


def test_cvat_pilot_imports_5_images_26_annotations(tmp_path: Path):
    export = tmp_path / "piloto.zip"
    output = tmp_path / "piloto_normalizado"
    make_cvat_zip(export)

    result = import_cvat(export, output, lote="piloto_v1")

    assert result["counts"] == {
        "imagenes": 5,
        "anotaciones": 26,
        "categorias_utilizadas": 2,
        "recuadros": 26,
    }
    candidates = read_csv(output / "candidatos.csv")
    annotations = read_csv(output / "anotaciones.csv")
    assert len(candidates) == 5
    assert len(annotations) == 26
    validation = validate(output)
    assert validation["valid"]
    assert validation["counts"]["candidatas"] == 5
    assert validation["counts"]["aceptadas"] == 0
    assert all(
        len(json.loads(row["bbox_homelens_yxyx"])) == 4
        for row in annotations
    )


def test_cvat_import_rejects_duplicate_annotation_image_ids(tmp_path: Path):
    export = tmp_path / "invalido.zip"
    coco = {
        "images": [
            {"id": 1, "width": 100, "height": 100, "file_name": "a.jpg"},
            {"id": 1, "width": 100, "height": 100, "file_name": "b.jpg"},
        ],
        "categories": [{"id": 1, "name": "Chair"}],
        "annotations": [],
    }
    with zipfile.ZipFile(export, "w") as archive:
        archive.writestr("annotations/instances_default.json", json.dumps(coco))

    try:
        import_cvat(export, tmp_path / "output")
        assert False, "Debería rechazar IDs COCO de imagen duplicados"
    except ValueError:
        pass


def test_cvat_import_associates_originals_and_verifies_dimensions(tmp_path: Path):
    export = tmp_path / "piloto.zip"
    output = tmp_path / "cvat" / "pilotos" / "piloto_v1"
    photos = tmp_path / "cvat" / "fotografias_originales" / "piloto_v1"
    make_cvat_zip(export, image_count=1, annotation_count=1)
    photos.mkdir(parents=True)
    photo = photos / "image_1.jpg"
    Image.new("RGB", (1000, 800), "white").save(photo, format="JPEG")

    result = import_cvat(
        export,
        output,
        lote="piloto_v1",
        destino="piloto",
        fotografias_originales=photos,
    )

    candidates = read_csv(output / "candidatos.csv")
    assert candidates[0]["estado_descarga"] == "fotografia_original_disponible"
    assert candidates[0]["ruta_relativa"]
    assert candidates[0]["sha256"] == sha256_file(photo)
    assert validate(output)["valid"]


def test_homelens_box_conversion_is_single_and_axis_correct():
    css = homelens_box_to_css([611, 516, 749, 683])
    assert abs(css["left"] - 51.6) < 0.0001
    assert abs(css["top"] - 61.1) < 0.0001
    assert abs(css["width"] - 16.7) < 0.0001
    assert abs(css["height"] - 13.8) < 0.0001


def test_gallery_uses_image_geometry_not_card_aspect_ratio(tmp_path: Path):
    candidates = tmp_path / "candidatos.csv"
    annotations = tmp_path / "anotaciones.csv"
    with candidates.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["image_id", "ruta_relativa", "nombre_archivo", "cantidad_objetos", "categorias", "ambiente", "iluminacion", "puntaje_domestico"],
        )
        writer.writeheader()
        writer.writerow({
            "image_id": "cvat_test_1",
            "ruta_relativa": "image.jpg",
            "nombre_archivo": "image.jpg",
            "cantidad_objetos": "2",
            "categorias": "Mirror,Sink",
            "ambiente": "baño",
            "iluminacion": "pendiente",
            "puntaje_domestico": "0",
        })
    with annotations.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["image_id", "categoria", "bbox_homelens_yxyx"],
        )
        writer.writeheader()
        writer.writerow({"image_id": "cvat_test_1", "categoria": "Mirror", "bbox_homelens_yxyx": "[53,44,497,251]"})
        writer.writerow({"image_id": "cvat_test_1", "categoria": "Sink", "bbox_homelens_yxyx": "[564,106,664,375]"})

    output = generate(tmp_path, tmp_path / "revision_visual.html")
    page = output.read_text(encoding="utf-8")
    assert 'object-fit' not in page
    assert 'aspect-ratio:' not in page
    assert 'class="image-wrap"' in page
    assert page.count('class="box"') == 2
    assert 'left:4.4000%;top:5.3000%;width:20.7000%;height:44.4000%' in page


def test_gallery_is_simplified_and_exports_review_decisions(tmp_path: Path):
    candidates = tmp_path / "candidatos.csv"
    with candidates.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["image_id", "ruta_relativa", "nombre_archivo", "open_images_id", "aceptada", "observaciones"],
        )
        writer.writeheader()
        writer.writerow({
            "image_id": "cvat_test_1",
            "ruta_relativa": "image.jpg",
            "nombre_archivo": "image.jpg",
            "open_images_id": "",
            "aceptada": "pendiente",
            "observaciones": "",
        })

    output = generate(tmp_path, tmp_path / "revision_visual.html")
    page = output.read_text(encoding="utf-8")
    assert "¿Anotaciones correctas?" in page
    assert "Pendiente de revisar" in page
    assert "Observaciones" in page
    assert "Puntaje:" not in page
    assert ">Ambiente<" not in page
    assert ">Iluminación<" not in page
    assert ">Dificultad<" not in page
    assert '"image_id","open_images_id","ruta_relativa","aceptada","observaciones"' in page


def test_review_import_updates_decisions_and_selection(tmp_path: Path):
    candidates = tmp_path / "candidatos.csv"
    with candidates.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "image_id", "open_images_id", "ruta_relativa", "aceptada",
            "observaciones", "estado_revision", "destino", "ambiente",
        ])
        writer.writeheader()
        writer.writerow({
            "image_id": "cvat_piloto_v1_1",
            "open_images_id": "",
            "ruta_relativa": "foto.jpg",
            "aceptada": "pendiente",
            "observaciones": "",
            "estado_revision": "",
            "destino": "piloto",
            "ambiente": "pendiente",
        })
    review = tmp_path / "seleccion_revision.csv"
    with review.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "image_id", "open_images_id", "ruta_relativa", "aceptada",
            "observaciones", "ambiente", "iluminacion", "dificultad",
            "motivo_descarte", "destino", "estado_revision",
        ])
        writer.writeheader()
        writer.writerow({
            "image_id": "cvat_piloto_v1_1",
            "open_images_id": "",
            "ruta_relativa": "foto.jpg",
            "aceptada": "si",
            "observaciones": "",
            "ambiente": "pendiente",
            "iluminacion": "",
            "dificultad": "",
            "motivo_descarte": "",
            "destino": "piloto",
            "estado_revision": "revisada",
        })

    result = importar_revision(tmp_path, review)

    updated = read_csv(candidates)[0]
    selection = read_csv(tmp_path / "seleccion.csv")[0]
    assert result["decisiones"] == 1
    assert result["aceptadas"] == 1
    assert updated["aceptada"] == "si"
    assert updated["estado_revision"] == "revisada"
    assert selection["image_id"] == "cvat_piloto_v1_1"


def test_cvat_reimport_preserves_human_review(tmp_path: Path):
    export = tmp_path / "piloto.zip"
    output = tmp_path / "piloto_v1"
    make_cvat_zip(export, image_count=1, annotation_count=1)
    photos = tmp_path / "originales"
    photos.mkdir()
    Image.new("RGB", (1000, 800), "white").save(photos / "image_1.jpg", format="JPEG")

    import_cvat(export, output, lote="piloto_v1", fotografias_originales=photos)
    candidates = read_csv(output / "candidatos.csv")
    candidates[0]["aceptada"] = "si"
    candidates[0]["observaciones"] = "Revisión humana"
    candidates[0]["estado_revision"] = "revisada"
    candidate_fields = list(candidates[0].keys())
    write_csv(output / "candidatos.csv", candidate_fields, candidates)

    import_cvat(export, output, lote="piloto_v1", fotografias_originales=photos)
    reimported = read_csv(output / "candidatos.csv")[0]
    assert reimported["aceptada"] == "si"
    assert reimported["observaciones"] == "Revisión humana"
    assert reimported["estado_revision"] == "revisada"


def test_living_aspect_ratio_and_validated_resize(tmp_path: Path):
    coco_width, coco_height = 1200, 2133
    actual_width, actual_height = 900, 1600
    ratio_difference = abs(
        coco_width / coco_height - actual_width / actual_height
    )
    assert ratio_difference < 0.001

    image_dir = tmp_path / "imagenes"
    image_dir.mkdir()
    photo = image_dir / "Living.jpg.jpeg"
    Image.new("RGB", (actual_width, actual_height), "white").save(photo)
    with (tmp_path / "candidatos.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "image_id", "fuente", "nombre_archivo", "ruta_relativa",
            "estado_descarga", "cantidad_objetos", "sha256", "aceptada",
        ])
        writer.writeheader()
        writer.writerow({
            "image_id": "cvat_piloto_v1_5",
            "fuente": "CVAT",
            "nombre_archivo": "Living.jpg",
            "ruta_relativa": "imagenes/Living.jpg.jpeg",
            "estado_descarga": "fotografia_original_transformacion_validada",
            "cantidad_objetos": "5",
            "sha256": sha256_file(photo),
            "aceptada": "si",
        })
    (tmp_path / "imagenes_normalizadas.json").write_text(json.dumps([{
        "file_name": "Living.jpg",
        "width": coco_width,
        "height": coco_height,
        "actual_width": actual_width,
        "actual_height": actual_height,
        "actual_format": "JPEG",
        "transformacion_validada": {
            "method": "uniform_resize_same_aspect_ratio",
            "coco_width": coco_width,
            "coco_height": coco_height,
            "actual_width": actual_width,
            "actual_height": actual_height,
            "ratio_difference": ratio_difference,
            "visual_review_accepted": True,
        },
    }]), encoding="utf-8")
    result = validate(tmp_path)
    assert result["valid"]
    assert any("Transformación validada" in warning for warning in result["warnings"])


def test_normalized_boxes_remain_precise_after_living_resize():
    box = [611, 516, 749, 683]
    ymin, xmin, ymax, xmax = [value / 1000 for value in box]
    scaled_x = (xmin * 900, xmax * 900)
    scaled_y = (ymin * 1600, ymax * 1600)
    expected = (464.4, 614.7, 977.6, 1198.4)
    actual = (scaled_x[0], scaled_x[1], scaled_y[0], scaled_y[1])
    assert all(abs(actual[index] - expected[index]) < 0.0001 for index in range(4))


def test_cvat_png_names_with_real_jpeg_format_are_metadata_only(tmp_path: Path):
    photo_dir = tmp_path / "imagenes"
    photo_dir.mkdir()
    for name, color in (
        ("Comedor01.png.jpeg", "white"),
        ("Dormitorio04.png.jpeg", "black"),
    ):
        Image.new("RGB", (1448, 1086), color).save(photo_dir / name)
    candidates = []
    for index, (name, actual_name) in enumerate((
        ("Comedor01.png", "Comedor01.png.jpeg"),
        ("Dormitorio04.png", "Dormitorio04.png.jpeg"),
    ), start=1):
        photo = photo_dir / actual_name
        candidates.append({
            "image_id": f"cvat_piloto_v1_{index + 2}",
            "fuente": "CVAT",
            "nombre_archivo": name,
            "ruta_relativa": f"imagenes/{photo.name}",
            "estado_descarga": "fotografia_original_disponible",
            "cantidad_objetos": "1",
            "sha256": sha256_file(photo),
            "aceptada": "si",
        })
    with (tmp_path / "candidatos.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(candidates[0].keys()))
        writer.writeheader()
        writer.writerows(candidates)
    result = validate(tmp_path)
    assert result["valid"]
