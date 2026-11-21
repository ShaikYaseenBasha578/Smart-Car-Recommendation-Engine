from pathlib import Path

import pytest

import services.images as images
from services.catalogue import get_catalogue
from services.images import find_car_image, get_manifest, image_attribution

ROOT = str(Path(__file__).resolve().parents[1])
LICENSE = "OEM brochure — not licensed for reuse; replace for commercial use"
PLACEHOLDERS = "/static/car_images/placeholders/"

# Catalogue models with no brochure image. Each one has no photo in a maker brochure on disk (Thar Roxx: the brochure
# is a 3-page specification sheet; Hector Plus: the Hector brochure names it once, in an accessories line; Bolero Neo
# Plus and Tekton: no brochure on disk). Nothing is fabricated: add a manifest row and a file, then remove it here.
NO_IMAGE_MODELS = ["Thar Roxx", "Hector Plus", "Bolero Neo Plus", "Tekton"]
NEW_IMAGE_COUNT = 28   # added from the brochures in knowledge_base/sources/oem_kbpipe (and Creta from sources/oem)


def manifest_urls():
    return {f"/static/car_images/{r['filename']}" for r in get_manifest().values()}


def test_manifest_has_brochure_images_only():
    manifest = get_manifest()
    assert len(manifest) == 60 + NEW_IMAGE_COUNT
    for (make, _), r in manifest.items():
        assert r["filename"].endswith(".webp")
        assert (Path(ROOT) / "static" / "car_images" / r["filename"]).exists(), r["filename"]
        assert r["license"] == LICENSE and r["attribution"] == f"{make} brochure"
        assert ".pdf, p." in r["source"]
        assert r["attribution"] and r["filename"] == Path(r["filename"]).name


def test_every_catalogue_model_gets_a_manifest_image_or_a_placeholder():
    cars = get_catalogue()[["make", "model", "body_type"]].drop_duplicates(["make", "model"])
    allowed = manifest_urls()
    for make, model, body_type in cars.itertuples(index=False):
        url = find_car_image(ROOT, make, model, body_type)
        assert url in allowed or url == f"{PLACEHOLDERS}{body_type}.svg", (make, model, url)
        assert (Path(ROOT) / url.lstrip("/")).exists()
    placeholders = {(make, model) for make, model, body_type in cars.itertuples(index=False)
                    if find_car_image(ROOT, make, model, body_type).startswith(PLACEHOLDERS)}
    # the models shown as a silhouette are exactly the ones with no row in image_manifest.csv (nothing is fabricated);
    # so a model with a manifest row whose file is missing is a silhouette without being in this set, and fails here
    manifest_models = set(get_manifest())
    assert placeholders == {(mk, md) for mk, md, _ in cars.itertuples(index=False)} - manifest_models
    if len(get_catalogue()) == 1464:       # the four known ones on the 1,464-variant catalogue
        assert set(NO_IMAGE_MODELS) <= {md for _, md in placeholders}


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
    assert image_attribution(ROOT, "Hyundai", "Creta") == "Hyundai brochure"
    assert image_attribution(ROOT, "Mahindra", "Thar Roxx") is None


def test_new_brochure_rows_record_pdf_page_and_sha1():
    import re
    new = [r for r in get_manifest().values() if "SHA-1" in r["source"]]
    assert len(new) == NEW_IMAGE_COUNT
    for r in new:
        assert re.fullmatch(r".+\.pdf, p\.\d+, SHA-1 [0-9a-f]{40}", r["source"]), r
    assert not {m for m in NO_IMAGE_MODELS} & {r["model"] for r in get_manifest().values()}


def test_new_images_are_small_webp_files():
    for r in get_manifest().values():
        data = (Path(ROOT) / "static" / "car_images" / r["filename"]).read_bytes()
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) < 100_000, r["filename"]


def test_new_images_are_small_800px_webp_without_metadata():
    Image = pytest.importorskip("PIL.Image")   # Pillow is a build-time tool here, not a runtime dependency
    new = [r for r in get_manifest().values() if "SHA-1" in r["source"]]
    for r in new:
        path = Path(ROOT) / "static" / "car_images" / r["filename"]
        assert path.stat().st_size < 100_000, path
        with Image.open(path) as im:
            assert im.format == "WEBP" and im.width == 800 and not im.info.get("exif"), path


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
