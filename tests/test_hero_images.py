"""The homepage hero mosaic only shows brochure images listed in data/image_manifest.csv."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERO = json.loads((ROOT / "static" / "hero_images.json").read_text(encoding="utf-8"))


def manifest_rows():
    with (ROOT / "data" / "image_manifest.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_every_hero_entry_maps_to_a_manifest_row():
    by_stem = {Path(r["filename"]).stem: r for r in manifest_rows()}
    assert len(HERO) >= 12
    for entry in HERO:
        stem = Path(entry["src"]).stem
        assert stem in by_stem, entry
        row = by_stem[stem]
        assert (entry["make"], entry["model"]) == (row["make"], row["model"]), entry
        assert entry["alt"] == f"{row['make']} {row['model']}"


def test_hero_thumbnails_exist_and_are_local():
    for entry in HERO:
        assert entry["src"].startswith("/static/car_images/hero/"), entry
        path = ROOT / entry["src"].lstrip("/")
        assert path.is_file(), path
        assert path.stat().st_size < 60_000, path


def test_homepage_serves_hero_assets():
    from app import app
    client = app.test_client()
    assert client.get("/static/hero_images.json").get_json() == HERO
    html = client.get("/").get_data(as_text=True)
    assert 'id="hero-mosaic"' in html
    assert 'id="how-it-works"' in html
    for banned in ("cdn.tailwindcss.com", "fonts.googleapis.com", "ML Intent", "Execute", "/new_cars"):
        assert banned not in html, banned
