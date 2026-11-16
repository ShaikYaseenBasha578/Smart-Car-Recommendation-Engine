"""Image step: synthetic PDFs, a temporary app repo. No network, no LLM."""
import csv
import io
import json
import os

import fitz
import pytest
from PIL import Image, ImageDraw

from kbpipe import images


def car_png(w=1400, h=800, seed=0):
    """A busy, colourful picture with a 'car' blob in the middle of a flat sky/road."""
    im = Image.new("RGB", (w, h), (200, 220, 240))
    d = ImageDraw.Draw(im)
    d.rectangle([0, int(h * 0.7), w, h], fill=(70, 70, 75))
    for i in range(40):
        x = (i * 97 + seed * 31) % w
        d.line([x, int(h * 0.7), x + 20, h], fill=(120, 120, 120), width=2)
    d.rounded_rectangle([w * 0.2, h * 0.35, w * 0.8, h * 0.72], 40, fill=(180, 20 + seed * 30, 30))
    d.rectangle([w * 0.3, h * 0.25, w * 0.65, h * 0.4], fill=(40, 60, 90))
    for cx in (0.3, 0.7):
        d.ellipse([w * cx - 60, h * 0.65, w * cx + 60, h * 0.65 + 120], fill=(15, 15, 15))
        d.ellipse([w * cx - 25, h * 0.65 + 35, w * cx + 25, h * 0.65 + 85], fill=(200, 200, 200))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def logo_png():
    im = Image.new("RGB", (300, 300), (255, 255, 255))
    ImageDraw.Draw(im).ellipse([60, 60, 240, 240], fill=(0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def make_brochure(path, hero_page=2, text_heavy=True):
    d = fitz.open()
    for n in range(1, 6):
        pg = d.new_page(width=842, height=595)
        if n == hero_page:
            pg.insert_image(fitz.Rect(0, 0, 842, 480), stream=car_png())
            pg.insert_text((40, 540), "Sleek outside.", fontsize=18)
        elif n == 3:
            pg.insert_image(fitz.Rect(20, 20, 70, 70), stream=logo_png())
            if text_heavy:
                pg.insert_textbox(fitz.Rect(30, 90, 810, 570), "Specifications and features. " * 120, fontsize=9)
        elif n == 4:   # a small car picture drowned in text: must rank below the hero
            pg.insert_image(fitz.Rect(300, 100, 560, 260), stream=car_png(seed=2))
            pg.insert_textbox(fitz.Rect(30, 280, 810, 570), "Specifications and features. " * 120, fontsize=9)
    d.save(path)
    d.close()
    return path


@pytest.fixture
def world(tmp_path):
    app = tmp_path / "app"
    (app / "data" / "catalogue_v3").mkdir(parents=True)
    (app / "static" / "car_images").mkdir(parents=True)
    with open(app / "data" / "catalogue_v3" / "catalogue.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["make", "model", "body_type", "price"])
        for mk, md in [("Tata", "Punch"), ("Tata", "Nexon"), ("Nissan", "Tekton"), ("Kia", "Sonet")]:
            w.writerow([mk, md, "suv", 1])
            w.writerow([mk, md, "suv", 2])
    with open(app / "data" / "image_manifest.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["make", "model", "filename", "source", "license", "attribution"])
        w.writerow(["Tata", "Nexon", "tata_nexon.webp", "x.pdf, p.1", images.LICENSE, "Tata brochure"])
    (app / "static" / "car_images" / "tata_nexon.webp").write_bytes(b"old")
    oem = tmp_path / "oem"
    new = tmp_path / "oem_new"
    (new / "tata" / "punch").mkdir(parents=True)
    (new / "kia" / "sonet").mkdir(parents=True)
    make_brochure(str(new / "tata" / "punch" / "p.pdf"), hero_page=2)
    # Sonet: two near-identical heroes -> no clear lead is not required, but a text-only PDF must give no pick
    d = fitz.open()
    pg = d.new_page()
    pg.insert_textbox(fitz.Rect(30, 30, 560, 800), "Only words here. " * 200, fontsize=10)
    d.save(str(new / "kia" / "sonet" / "s.pdf"))
    d.close()
    man = {"Tata/Punch": {"path": "tata/punch/p.pdf"}, "Kia/Sonet": {"path": "kia/sonet/s.pdf"}}
    (new / "brochure_manifest.json").write_text(json.dumps(man))
    oem.mkdir()
    (oem / "brochure_manifest.json").write_text("{}")
    return app, str(oem), str(new), tmp_path


def test_lists_only_models_without_image(world):
    app, *_ = world
    assert images.models_without_image(str(app)) == [("Tata", "Punch", "suv"), ("Nissan", "Tekton", "suv"),
                                                      ("Kia", "Sonet", "suv")]


def test_dry_run_writes_only_the_run_folder_and_never_picks_blindly(world):
    app, oem, new, tmp = world
    before = {p: os.path.getmtime(p) for p in [app / "data" / "image_manifest.csv"]}
    res = images.run(str(app), oem, new, run_dir=str(tmp / "run"))
    assert res["no_brochure"] == ["Nissan/Tekton"]
    punch = res["picks"]["tata_punch"]
    assert 1 <= len(punch["candidates"]) <= 3
    # the full-width hero on page 2 beats the logo and the text-heavy pages
    assert punch["candidates"][0]["page"] == 2
    assert punch["choice"] == 1 and not punch["needs_human"]
    assert os.path.isfile(tmp / "run" / "contact_sheet.html")
    assert os.path.isfile(tmp / "run" / punch["candidates"][0]["file"])
    sonet = res["picks"].get("kia_sonet")
    assert sonet is None or sonet["choice"] is None      # text-only brochure: nothing is picked
    assert not (app / "static" / "car_images" / "tata_punch.webp").exists()
    assert before[app / "data" / "image_manifest.csv"] == os.path.getmtime(app / "data" / "image_manifest.csv")


def test_apply_matches_the_existing_format_and_records_source(world):
    app, oem, new, tmp = world
    res = images.run(str(app), oem, new, run_dir=str(tmp / "run"))
    out = images.apply_picks(str(tmp / "run" / "picks.json"))
    assert out["applied"] == ["tata_punch"]
    target = app / "static" / "car_images" / "tata_punch.webp"
    with Image.open(target) as im:
        assert im.format == "WEBP" and im.width == 800 and "exif" not in im.info
    assert target.stat().st_size < 100_000
    rows = {(r["make"], r["model"]): r for r in csv.DictReader(open(app / "data" / "image_manifest.csv"))}
    r = rows[("Tata", "Punch")]
    sha = res["picks"]["tata_punch"]["candidates"][0]["pdf_sha1"]
    assert r["filename"] == "tata_punch.webp" and r["attribution"] == "Tata brochure"
    assert r["license"] == images.LICENSE and ".pdf, p.2" in r["source"] and sha in r["source"]
    assert rows[("Tata", "Nexon")]["filename"] == "tata_nexon.webp"


def test_apply_refuses_to_overwrite_unless_replace(world):
    app, oem, new, tmp = world
    images.run(str(app), oem, new, run_dir=str(tmp / "run"))
    images.apply_picks(str(tmp / "run" / "picks.json"))
    first = (app / "static" / "car_images" / "tata_punch.webp").read_bytes()
    again = images.apply_picks(str(tmp / "run" / "picks.json"))
    assert again["applied"] == [] and "already has an image" in again["skipped"][0][1]
    assert (app / "static" / "car_images" / "tata_punch.webp").read_bytes() == first
    assert images.apply_picks(str(tmp / "run" / "picks.json"), replace=True)["applied"] == ["tata_punch"]
    # an existing model's image (Nexon) is never touched without a pick for it
    assert (app / "static" / "car_images" / "tata_nexon.webp").read_bytes() == b"old"


def test_null_choice_is_skipped_and_changed_pdf_is_refused(world):
    app, oem, new, tmp = world
    images.run(str(app), oem, new, run_dir=str(tmp / "run"))
    picks = json.load(open(tmp / "run" / "picks.json"))
    picks["picks"]["tata_punch"]["choice"] = None
    json.dump(picks, open(tmp / "run" / "picks.json", "w"))
    assert images.apply_picks(str(tmp / "run" / "picks.json"))["applied"] == []
    picks["picks"]["tata_punch"]["choice"] = 1
    json.dump(picks, open(tmp / "run" / "picks.json", "w"))
    with open(new + "/tata/punch/p.pdf", "ab") as f:
        f.write(b"\n%tamper")
    out = images.apply_picks(str(tmp / "run" / "picks.json"))
    assert out["applied"] == [] and "changed" in out["skipped"][0][1]


def test_find_brochures_is_exact_model_only(world):
    app, oem, new, tmp = world
    assert images.find_brochures("Tata", "Punch", oem, new)
    assert images.find_brochures("Tata", "Punch EV", oem, new) == []
    assert images.find_brochures("Tata", "Sierra", oem, new) == []


def test_score_prefers_wide_clean_early_pictures():
    m = {"colour": 40, "edge": 0.12, "centre_ratio": 1.6, "flat": 0.5, "luma": 130}
    good, _ = images.score({"width": 1600, "height": 900, "page": 1, "text_frac": 0.0}, m)
    texty, _ = images.score({"width": 1600, "height": 900, "page": 1, "text_frac": 0.4}, m)
    late, _ = images.score({"width": 1600, "height": 900, "page": 12, "text_frac": 0.0}, m)
    tall, _ = images.score({"width": 700, "height": 1600, "page": 1, "text_frac": 0.0}, m)
    assert good > texty and good > late and good > tall


def test_crop_fraction_is_a_plain_rectangle_and_ignores_bad_boxes():
    im = Image.new("RGB", (1000, 500), (10, 20, 30))
    assert images.crop_fraction(im, [0.1, 0.2, 0.6, 0.8]).size == (500, 300)
    assert images.crop_fraction(im, None) is im
    assert images.crop_fraction(im, [0.6, 0.2, 0.1, 0.8]) is im


def test_salient_window_finds_the_busy_band_of_a_tall_picture():
    im = Image.new("RGB", (400, 1200), (200, 220, 240))
    d = ImageDraw.Draw(im)
    for i in range(30):       # busy, colourful band in the lower middle
        d.rectangle([20 + i * 12, 700 + (i % 5) * 30, 40 + i * 12, 800 + (i % 5) * 30], fill=(200, 20 + i * 6, 40))
    top, bot = images.salient_window(im)
    assert 0.45 < (top + bot) / 2 < 0.8 and bot - top < 0.5


def test_candidates_without_a_brochure_are_listed_and_never_downloaded(world, monkeypatch):
    import socket
    def no_net(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", no_net)
    app, oem, new, tmp = world
    res = images.run(str(app), oem, new, run_dir=str(tmp / "run"))
    assert "Nissan/Tekton" in res["no_brochure"]
