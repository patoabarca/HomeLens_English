import csv
from pathlib import Path

from PIL import Image

from scripts.evaluacion.evaluacion_common import coco_to_homelens, read_csv, sha256_file
from scripts.evaluacion.validar_dataset import validate


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
