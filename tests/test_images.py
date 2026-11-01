from pathlib import Path

import pytest

import services.images as images
from services.catalogue import get_catalogue
from services.images import find_car_image, get_manifest, image_attribution

ROOT = str(Path(__file__).resolve().parents[1])
LICENSE = "OEM brochure — not licensed for reuse; replace for commercial use"
PLACEHOLDERS = "/static/car_images/placeholders/"


def manifest_urls():
    return {f"/static/car_images/{r['filename']}" for r in get_manifest().values()}


def test_manifest_has_brochure_images_only():
    manifest = get_manifest()
    assert len(manifest) == 60
    for (make, _), r in manifest.items():
        assert r["filename"].endswith(".webp")
        assert (Path(ROOT) / "static" / "car_images" / r["filename"]).exists(), r["filename"]
        assert r["license"] == LICENSE and r["attribution"] == f"{make} brochure"
        assert ".pdf, p." in r["source"]


def test_every_catalogue_model_gets_a_manifest_image_or_a_placeholder():
    cars = get_catalogue()[["make", "model", "body_type"]].drop_duplicates(["make", "model"])
    allowed = manifest_urls()
    for make, model, body_type in cars.itertuples(index=False):
        url = find_car_image(ROOT, make, model, body_type)
        assert url in allowed or url == f"{PLACEHOLDERS}{body_type}.svg", (make, model, url)
        assert (Path(ROOT) / url.lstrip("/")).exists()
    placeholders = [model for make, model, body_type in cars.itertuples(index=False)
                    if find_car_image(ROOT, make, model, body_type).startswith(PLACEHOLDERS)]
    assert sorted(placeholders) == ["Creta", "Thar Roxx"]


def test_manifest_then_placeholder_never_a_filename(monkeypatch):
    # manifest wins
    monkeypatch.setitem(images._MANIFEST, ("Hyundai", "Creta"),
                        {"filename": "hyundai_venue.webp", "attribution": "Hyundai brochure"})
    assert find_car_image(ROOT, "Hyundai", "Creta", "suv") == "/static/car_images/hyundai_venue.webp"
    assert image_attribution(ROOT, "Hyundai", "Creta") == "Hyundai brochure"
    # manifest file missing: silhouette, no caption (no lookup of hyundai_creta.jpg etc.)
    monkeypatch.setitem(images._MANIFEST, ("Hyundai", "Creta"),
                        {"filename": "nope.webp", "attribution": "Hyundai brochure"})
    assert find_car_image(ROOT, "Hyundai", "Creta", "suv") == f"{PLACEHOLDERS}suv.svg"
    assert image_attribution(ROOT, "Hyundai", "Creta") is None
    # not in the manifest: silhouette; no body type: the generic image
    assert find_car_image(ROOT, "Mahindra", "Thar Roxx", "suv") == f"{PLACEHOLDERS}suv.svg"
    assert find_car_image(ROOT, "Audi", "A6") == "/static/car_images/pic1.avif"


def test_brochure_images_have_captions():
    assert find_car_image(ROOT, "Maruti Suzuki", "Fronx", "suv") == "/static/car_images/maruti_suzuki_fronx.webp"
    assert image_attribution(ROOT, "Maruti Suzuki", "Fronx") == "Maruti Suzuki brochure"
    assert find_car_image(ROOT, "Tata", "Nexon", "suv") == "/static/car_images/tata_nexon.webp"
    assert image_attribution(ROOT, "Tata", "Nexon") == "Tata brochure"
    assert image_attribution(ROOT, "Hyundai", "Creta") is None


@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def test_response_carries_image_attribution(client, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "kb")
    recs = client.post("/predict", json={"query": "petrol SUV under 15 lakh"}).get_json()["recommendations"]
    assert recs and all("imageAttribution" in r for r in recs)


def test_legacy_path_serves_no_legacy_photo(client, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "legacy")
    recs = client.post("/predict", json={"query": "petrol SUV under 15 lakh"}).get_json()["recommendations"]
    assert recs
    for r in recs:
        assert r["carImage"] in manifest_urls() | {"/static/car_images/pic1.avif"}, r["carImage"]
