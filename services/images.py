"""Card images: data/image_manifest.csv first, then legacy filenames, then a body-type silhouette.

Manifest columns: make, model, filename (under static/car_images/), source, license, attribution.
A non-empty attribution is shown as a caption under the card image.
"""

from __future__ import annotations

import csv
import os

from services.catalogue import DATA_DIR

IMAGE_MANIFEST_CSV = DATA_DIR / "image_manifest.csv"


def _load_manifest() -> dict[tuple[str, str], dict]:
    with open(IMAGE_MANIFEST_CSV, newline="", encoding="utf-8") as fh:
        return {(r["make"], r["model"]): r for r in csv.DictReader(fh)}


_MANIFEST = _load_manifest()


def get_manifest() -> dict[tuple[str, str], dict]:
    return _MANIFEST


def _exists(app_root_path, *parts) -> bool:
    return os.path.exists(os.path.join(app_root_path, "static", "car_images", *parts))


def find_car_image(app_root_path, make, model, body_type=None):
    """Manifest file; then make_model.jpg / the hyphenated model name used by most legacy files;
    then an in-house body-type silhouette (static/car_images/placeholders/<body_type>.svg)."""
    entry = _MANIFEST.get((make, model))
    if entry and _exists(app_root_path, entry["filename"]):
        return f"/static/car_images/{entry['filename']}"

    make_part = str(make).lower().replace(" ", "_")
    model_part = str(model).lower()
    for image_filename in (
        f"{make_part}_{model_part.replace(' ', '_')}.jpg",
        f"{make_part}_{model_part.replace(' ', '-')}.jpg",
    ):
        if _exists(app_root_path, image_filename):
            return f"/static/car_images/{image_filename}"

    if body_type and _exists(app_root_path, "placeholders", f"{body_type}.svg"):
        return f"/static/car_images/placeholders/{body_type}.svg"

    return "/static/car_images/pic1.avif"


def image_attribution(app_root_path, make, model):
    """The manifest attribution for the image actually shown, or None."""
    entry = _MANIFEST.get((make, model))
    if entry and entry["attribution"] and _exists(app_root_path, entry["filename"]):
        return entry["attribution"]
    return None
