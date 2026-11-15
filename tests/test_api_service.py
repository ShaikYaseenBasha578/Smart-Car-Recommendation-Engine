"""FastAPI service (api_service/). The app is imported with API_SERVICE_NO_ENV=1 so this process keeps the catalogue the
rest of the suite uses; one subprocess test checks the service's own env (v3 catalogue)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    old = os.environ.get("API_SERVICE_NO_ENV")
    os.environ["API_SERVICE_NO_ENV"] = "1"
    try:
        from api_service.main import create_app
    finally:
        if old is None:
            os.environ.pop("API_SERVICE_NO_ENV", None)
        else:
            os.environ["API_SERVICE_NO_ENV"] = old
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c


QUERY = "family suv under 15 lakh automatic"


def _direct(query=QUERY):
    from services.recsys.api import recommend
    old = os.environ.get("LLM_PARSER")
    os.environ["LLM_PARSER"] = "off"
    try:
        return json.loads(json.dumps(recommend(query)))
    finally:
        os.environ.pop("LLM_PARSER", None) if old is None else os.environ.__setitem__("LLM_PARSER", old)


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["engine"] == "v3"
    assert body["catalogue_rows"] > 0 and body["catalogue_models"] > 0
    assert body["data_files"]["assessments_csv"]


def test_recommend_matches_engine(client):
    r = client.post("/v1/recommend", json={"query": QUERY, "limit": 5})
    assert r.status_code == 200
    body = r.json()
    direct = _direct()
    assert set(["engine", "query_understood", "results", "relaxed", "generated_at"]) <= set(body)
    assert body["engine"] == direct["engine"]
    assert body["query_understood"] == direct["intent"]
    assert body["results"] == direct["recommendations"][:5]
    assert body["relaxed"] == direct.get("relaxation")


def test_recommend_limit_and_relaxed(client):
    r = client.post("/v1/recommend", json={"query": QUERY, "limit": 1}).json()
    assert len(r["results"]) <= 1
    r = client.post("/v1/recommend", json={"query": "ev suv under 5 lakh with ventilated seats and 7 seats"}).json()
    assert r["relaxed"] is not None or r["results"] == [] or r["message"]


@pytest.mark.parametrize("body", [
    {"query": ""}, {"query": "   "}, {"query": "x" * 501}, {"query": "suv", "limit": 0}, {"query": "suv", "limit": 21},
    {"limit": 3}, {"query": "suv", "unknown": 1}, {"query": 5},
])
def test_recommend_validation_errors(client, body):
    r = client.post("/v1/recommend", json=body)
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"
    assert "Traceback" not in r.text


def test_llm_requested_without_key_stays_off(client, monkeypatch):
    for k in ("GEMINI_API_KEY", "LLM_PARSER_KEY_ENV", "LLM_PARSER_BASE_URL", "LLM_PARSER_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    body = client.post("/v1/recommend", json={"query": QUERY, "llm": True}).json()
    assert body["llm"]["used"] is False
    assert os.environ.get("LLM_PARSER") != "on"


def test_unexpected_error_hides_trace(client, monkeypatch):
    import api_service.main as main

    def boom(*a, **k):
        raise RuntimeError("secret internals")
    monkeypatch.setattr(main, "engine_recommend", boom)
    r = client.post("/v1/recommend", json={"query": QUERY})
    assert r.status_code == 500 and r.json()["error"] == "internal_error"
    assert "secret internals" not in r.text and "Traceback" not in r.text


def test_evidence_with_data(client):
    r = client.get("/v1/models/creta/evidence")
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "Creta" and body["in_catalogue"] and body["make"]
    assert body["expert_rows"] and all(row["url"] for row in body["expert_rows"])
    assert body["owner_ratings"] and body["owner_themes"]
    assert all(isinstance(t["sample_urls"], list) for t in body["owner_themes"])


def test_evidence_without_data_and_unknown(client):
    import pandas as pd
    from services.catalogue import get_catalogue
    from services.recsys import evidence as ev
    df = get_catalogue()
    reviewed = set(pd.read_csv(ev.ASSESSMENTS_CSV)["model"]) | set(pd.read_csv(ev.OWNER_RATINGS_CSV)["model"]) \
        | set(pd.read_csv(ev.OWNER_THEMES_CSV)["model"])
    bare = [m for m in df["model"].unique() if m not in reviewed]
    if bare:  # a catalogue model with no review rows: 200 with empty lists
        body = client.get(f"/v1/models/{bare[0]}/evidence").json()
        assert body["in_catalogue"] and body["expert_rows"] == [] and body["owner_ratings"] == [] and body["owner_themes"] == []
    r = client.get("/v1/models/NotACar/evidence")
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_compare(client):
    r = client.post("/v1/compare", json={"models": ["Creta", "Seltos"], "query": "automatic diesel"})
    assert r.status_code == 200
    body = r.json()
    assert [m["model"] for m in body["models"]] == ["Creta", "Seltos"]
    for m in body["models"]:
        assert m["found"] and m["card"]["Model"] == m["model"]


def test_compare_validation(client):
    assert client.post("/v1/compare", json={"models": ["Creta"]}).status_code == 422
    assert client.post("/v1/compare", json={"models": ["a", "b", "c", "d", "e"]}).status_code == 422
    assert client.post("/v1/compare", json={"models": ["Creta", "creta"]}).status_code == 422
    r = client.post("/v1/compare", json={"models": ["Creta", "Nopecar"]})
    assert r.status_code == 404 and r.json()["detail"]["models"] == ["Nopecar"]


def test_cors_off_by_default(client):
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_service_env_uses_v3_catalogue():
    code = ("from fastapi.testclient import TestClient\nfrom api_service.main import app\n"
            "print(TestClient(app).get('/health').json()['catalogue_rows'])")
    env = {k: v for k, v in os.environ.items() if k not in ("CARREC_CATALOGUE_DIR", "RANKER", "API_SERVICE_NO_ENV")}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    meta = json.loads((ROOT / "data" / "catalogue_v3" / "catalogue_meta.json").read_text())
    assert int(out.stdout.strip().splitlines()[-1]) == meta["row_count"]
