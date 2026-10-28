from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Iterable, Mapping, Sequence


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest().hex()


def coco_to_homelens(box: Sequence[float], image_width: int, image_height: int) -> list[int]:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Las dimensiones deben ser positivas")
    if len(box) != 4:
        raise ValueError("El bounding box debe tener cuatro valores: xmin, ymin, ancho, alto")

    xmin, ymin, width, height = box
    xmax = xmin + width
    ymax = ymin + height
    values = (ymin / image_height, xmin / image_width, ymax / image_height, xmax / image_width)
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("El bounding box queda fuera de la imagen")
    if ymin >= ymax or xmin >= xmax:
        raise ValueError("El bounding box debe tener area positiva")
    return [round(value * 1000) for value in values]


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: str | Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
