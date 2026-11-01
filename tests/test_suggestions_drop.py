import json
from pathlib import Path

import pytest

from services.intent_v2 import parse_intent
from services.new_car_service import apply_drops

ROOT = Path(__file__).resolve().parents[1]
SUGGESTIONS = json.loads((ROOT / "data" / "suggested_queries.json").read_text(encoding="utf-8"))
CATEGORIES = {"hinglish", "transmission", "features", "like_model", "safety", "ev", "budget", "family"}


@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def predict(client, monkeypatch, query, **extra):
    monkeypatch.setenv("DATA_SOURCE", "kb")
    response = client.post("/predict", json={"query": query, **extra})
    assert response.status_code == 200
    return response.get_json()


# --- suggested queries ---

def test_suggestions_file_shape():
    assert 18 <= len(SUGGESTIONS) <= 22
    assert {s["category"] for s in SUGGESTIONS} == CATEGORIES
    assert len({s["query"] for s in SUGGESTIONS}) == len(SUGGESTIONS)


def test_suggestions_served_from_static(client):
    assert client.get("/static/suggested_queries.json").get_json() == SUGGESTIONS


@pytest.mark.parametrize("query", [s["query"] for s in SUGGESTIONS])
def test_every_suggestion_returns_at_least_3_cards(client, monkeypatch, query):
    assert len(predict(client, monkeypatch, query)["recommendations"]) >= 3


# --- drop ---

def test_hints_carry_keys_and_dropping_one_returns_results(client, monkeypatch):
    hints = predict(client, monkeypatch, "CVT automatic hatchback")["relaxation_hints"]
    assert hints and all(h["key"] for h in hints)
    for h in hints:
        data = predict(client, monkeypatch, "CVT automatic hatchback", drop=[h["key"]])
        assert data["recommendations"]
        assert data["dropped"] == [{"key": h["key"], "label": h["drop"]}]


def test_drop_transmission_removes_it_from_the_intent(client, monkeypatch):
    data = predict(client, monkeypatch, "CVT automatic hatchback", drop=["transmission"])
    assert data["intent"]["transmission"] == {"family": None, "include_types": [], "exclude_types": []}
    assert data["intent"]["body_types"] == ["hatchback"]
    assert data["dropped"][0]["label"].endswith("transmission")


def test_unknown_or_inactive_keys_are_ignored(client, monkeypatch):
    data = predict(client, monkeypatch, "sedan with sunroof", drop=["seats", "feature:adas", "nonsense"])
    assert data["dropped"] == [] and data["recommendations"]


def test_no_drop_means_no_dropped_key(client, monkeypatch):
    assert "dropped" not in predict(client, monkeypatch, "sedan with sunroof")


def test_feature_drops_compose():
    intent = parse_intent("SUV with ADAS and 360 camera under 25 lakh")
    assert {"adas", "camera_360"} <= set(intent["required_features"])
    relaxed, dropped = apply_drops(intent, ["feature:adas", "feature:camera_360", "budget"])
    assert not {"adas", "camera_360"} & set(relaxed["required_features"])
    assert relaxed["budget"] == {"min": None, "max": None}
    assert [d["key"] for d in dropped] == ["feature:adas", "feature:camera_360", "budget"]
    assert apply_drops(intent, "budget")[1][0]["key"] == "budget"  # a single string is accepted
