"""With no environment variables the app runs ranking engine v3 on the default (exported) catalogue; the old engine and the
original 832-variant catalogue stay available (RANKER=current, CARREC_CATALOGUE_DIR=data). Each case runs in its own
process because the catalogue is chosen when `services.catalogue` is first imported."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _size(directory):
    """(rows, models) of the catalogue.csv in a directory: read from the file, so the tests follow the default catalogue."""
    import pandas as pd
    df = pd.read_csv(ROOT / directory / "catalogue.csv", usecols=["make", "model"])
    return len(df), int(df.drop_duplicates().shape[0])


DEFAULT_SIZE = _size("data/catalogue_v3")      # follows the exported default catalogue
OLD_SIZE = (832, 62)                           # the original catalogue stays fixed (CARREC_CATALOGUE_DIR=data)

PROBE = r"""
import contextlib, io, json
from app import app
from services.catalogue import get_catalogue
cat = get_catalogue()
app.config["TESTING"] = True
with contextlib.redirect_stdout(io.StringIO()):
    r = app.test_client().post("/predict", json={"query": "%s"}).get_json()
index = app.test_client().get("/").get_data(as_text=True)
print(json.dumps({"rows": len(cat), "models": int(cat[["make", "model"]].drop_duplicates().shape[0]),
                  "engine": r.get("engine"), "parser_used": r.get("parser_used"),
                  "n": len(r.get("recommendations") or []), "cards": [
                      {k: c.get(k) for k in ("Make", "Model", "carImage", "imageAttribution")}
                      for c in (r.get("recommendations") or [])],
                  "index_count": [(f"{__DEFAULT_ROWS__:,}" in index), ("832" in index)]}))
"""


def run(query, **env):
    base = {k: v for k, v in os.environ.items() if k not in ("RANKER", "CARREC_CATALOGUE_DIR", "API_SERVICE_NO_ENV")}
    base.update({"DATA_SOURCE": "kb", "LLM_PARSER": "off", **env})
    out = subprocess.run([sys.executable, "-c", PROBE.replace("__DEFAULT_ROWS__", str(DEFAULT_SIZE[0])) % query], cwd=ROOT, env=base, capture_output=True, text=True,
                         timeout=180)
    assert out.returncode == 0, out.stderr[-800:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_the_default_and_the_original_catalogues_differ():
    assert DEFAULT_SIZE != OLD_SIZE


def test_no_environment_means_v3_on_the_new_catalogue():
    r = run("comfortable family SUV under 15 lakh")
    assert (r["rows"], r["models"]) == DEFAULT_SIZE
    assert r["engine"] == "v3" and r["n"] >= 3
    assert r["index_count"] == [True, False]      # the home page states the catalogue size it actually uses


def test_old_engine_and_old_catalogue_still_work_when_selected():
    r = run("family suv under 15 lakh", RANKER="current", CARREC_CATALOGUE_DIR="data")
    assert (r["rows"], r["models"]) == OLD_SIZE
    assert r["engine"] is None and r["parser_used"] == "intent_v2" and r["n"] >= 3
    assert r["index_count"] == [False, True]


def test_old_engine_on_the_new_catalogue_and_v3_on_the_old_catalogue_are_independent_switches():
    assert run("family suv under 15 lakh", RANKER="current")["rows"] == DEFAULT_SIZE[0]
    r = run("family suv under 15 lakh", CARREC_CATALOGUE_DIR="data")
    assert r["rows"] == OLD_SIZE[0] and r["engine"] == "v3"


def test_a_relative_catalogue_path_is_taken_from_the_repository_root(tmp_path):
    r = run("family suv under 15 lakh", CARREC_CATALOGUE_DIR="data/catalogue_v3")
    assert r["rows"] == DEFAULT_SIZE[0]
    # same result when the process starts in another directory
    base = {k: v for k, v in os.environ.items() if k not in ("RANKER", "CARREC_CATALOGUE_DIR")}
    base["CARREC_CATALOGUE_DIR"] = "data"
    out = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {str(ROOT)!r}); "
                         "from services.catalogue import get_catalogue; print(len(get_catalogue()))"],
                         cwd=tmp_path, env=base, capture_output=True, text=True, timeout=120)
    assert out.stdout.strip() == "832", out.stderr[-500:]


def test_a_model_without_an_image_shows_the_body_type_silhouette_and_no_caption():
    r = run("Mahindra Thar Roxx")   # no usable brochure picture on disk (3-page specification sheet)
    cards = [c for c in r["cards"] if c["Model"] == "Thar Roxx"]
    assert cards, r["cards"]
    for c in cards:
        assert c["carImage"] == "/static/car_images/placeholders/suv.svg" and not c["imageAttribution"]
        assert (ROOT / c["carImage"].lstrip("/")).exists()
