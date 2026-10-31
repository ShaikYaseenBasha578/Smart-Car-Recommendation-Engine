from pathlib import Path

import pytest

import services.images as images
from services.images import find_car_image, get_manifest, image_attribution

ROOT = str(Path(__file__).resolve().parents[1])


def test_manifest_prefilled_with_legacy_images():
    manifest = get_manifest()
    assert len(manifest) >= 22
    legacy = [r for r in manifest.values() if r["source"] == "unknown — legacy"]
    assert len(legacy) == 22
    for r in manifest.values():
        assert (Path(ROOT) / "static" / "car_images" / r["filename"]).exists(), r["filename"]


def test_manifest_first_then_filename_then_placeholder(monkeypatch):
    # manifest points Creta at another existing file: manifest wins
    monkeypatch.setitem(images._MANIFEST, ("Hyundai", "Creta"),
                        {"filename": "hyundai_venue.jpg", "attribution": "Hyundai brochure"})
    assert find_car_image(ROOT, "Hyundai", "Creta", "suv") == "/static/car_images/hyundai_venue.jpg"
    assert image_attribution(ROOT, "Hyundai", "Creta") == "Hyundai brochure"
    # manifest file missing on disk: fall through to the legacy filename, no caption
    monkeypatch.setitem(images._MANIFEST, ("Hyundai", "Creta"),
                        {"filename": "nope.webp", "attribution": "Hyundai brochure"})
    assert find_car_image(ROOT, "Hyundai", "Creta", "suv") == "/static/car_images/hyundai_creta.jpg"
    assert image_attribution(ROOT, "Hyundai", "Creta") is None
    # nothing at all: body-type silhouette
    assert find_car_image(ROOT, "Maruti Suzuki", "Fronx", "suv") == "/static/car_images/placeholders/suv.svg"
    assert image_attribution(ROOT, "Maruti Suzuki", "Fronx") is None


def test_legacy_images_have_no_caption():
    assert image_attribution(ROOT, "Tata", "Nexon") is None


@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def test_response_carries_image_attribution(client, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "kb")
    recs = client.post("/predict", json={"query": "petrol SUV under 15 lakh"}).get_json()["recommendations"]
    assert recs and all("imageAttribution" in r for r in recs)
