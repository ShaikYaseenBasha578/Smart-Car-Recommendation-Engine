"""Step 2 parser repairs: negated features/makes, upper bounds, ML guesses as soft 'assumed', vague, unsupported-only."""

import pandas as pd
import pytest

from services import intent_v2
from services.catalogue import get_catalogue
from services.filter_v2 import filter_candidates
from services.intent_v2 import parse_intent
from services.ranking_adapter import rank_candidates
from tests.test_filter_v2 import frame, ids, intent


@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def predict(client, monkeypatch, query):
    monkeypatch.setenv("DATA_SOURCE", "kb")
    response = client.post("/predict", json={"query": query})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


# --- (c) ML guesses are assumed, never filters ---

def test_ml_body_and_fuel_guesses_are_assumed_not_filters(monkeypatch):
    monkeypatch.setattr(intent_v2, "_ml_predict", lambda q: {
        "body": ("suv", 0.9), "fuel": ("diesel", 0.8), "use_case": ("family", 0.7)})
    out = parse_intent("something rugged for the family")
    assert out["body_types"] == [] and out["fuel_types"] == []
    assert out["assumed"] == {"body_types": ["suv"], "fuel_types": ["diesel"]}
    assert out["use_case"] == "family"  # use_case behaves as before
    assert any("assumed" in t for t in out["trace"])
    # a guess never makes a vague query look specific
    assert out["vague"] is False  # use-case words count only if the rules saw them; here "family" is a rule hit
    vague = parse_intent("good car")
    assert vague["vague"] is True and vague["assumed"]["body_types"] == ["suv"]


def test_ml_does_not_override_stated_fields(monkeypatch):
    monkeypatch.setattr(intent_v2, "_ml_predict", lambda q: {
        "body": ("suv", 0.9), "fuel": ("diesel", 0.8), "use_case": ("family", 0.7)})
    out = parse_intent("petrol hatchback")
    assert out["assumed"] == {"body_types": [], "fuel_types": []}
    assert out["fuel_types"] == ["petrol"] and out["body_types"] == ["hatchback"]


def test_assumed_gives_a_bounded_boost_and_does_not_filter():
    df = frame({"body_type": "suv"}, {"body_type": "hatchback"})
    it = intent(assumed={"body_types": ["suv"], "fuel_types": []})
    cand = filter_candidates(it, df)
    assert ids(cand) == [1, 2]  # nothing filtered
    ranked, _ = rank_candidates(it, cand)
    assert ranked.iloc[0]["variant_id"] == 1
    assert any("assumed body suv" in r for r in ranked.iloc[0]["match_reasons"])


# --- (a) exclusions through the filter, same tri-state rule ---

def test_exclude_makes_is_a_hard_filter():
    df = frame({"make": "Tata"}, {"make": "Kia"}, {"make": "Hyundai"})
    assert ids(filter_candidates(intent(exclude_makes=["Tata", "Kia"]), df)) == [3]


def test_exclude_features_tristate():
    df = frame({"sunroof": True}, {"sunroof": False},
               {"sunroof": None, "unverified_fields": frozenset({"sunroof"})},
               {"sunroof": True, "unverified_fields": frozenset({"sunroof"})})
    out = filter_candidates(intent(exclude_features=["sunroof"]), df)
    assert ids(out) == [2, 3, 4]  # known present is excluded; unknown (blank or unverified) is kept and flagged
    assert out.loc[2, "unverified"] == []
    assert out.loc[3, "unverified"] == ["Unverified: no sunroof"]
    assert out.loc[4, "unverified"] == ["Unverified: no sunroof"]


# --- (b) upper bounds ---

def test_max_bounds_tristate():
    df = frame({"ground_clearance_mm": 170.0}, {"ground_clearance_mm": 200.0}, {"ground_clearance_mm": float("nan")},
               {"ground_clearance_mm": float("nan"), "unverified_fields": frozenset({"ground_clearance_mm"})})
    out = filter_candidates(intent(max_ground_clearance_mm=180.0), df)
    assert ids(out) == [1, 4]  # blank and not unverified = not applicable: excluded; unverified: kept
    assert out.loc[4, "unverified"] == ["Unverified: ground clearance"]


def test_max_mileage_units_not_mixed():
    df = frame({"fuel_type": "cng", "mileage_km_per_kg": 26.0}, {"fuel_type": "cng", "mileage_km_per_kg": 33.0},
               {"fuel_type": "petrol", "mileage_km_per_kg": float("nan")})
    assert ids(filter_candidates(intent(max_mileage_km_per_kg=30.0), df)) == [1]


def test_upper_bound_not_read_as_minimum():
    got = parse_intent("boot space under 300 litres", use_ml=False)
    assert got["max_boot_space_litres"] == 300 and got["min_boot_space_litres"] is None
    assert got["budget"] == {"min": None, "max": None}
    got = parse_intent("ground clearance below 180 mm", use_ml=False)
    assert got["max_ground_clearance_mm"] == 180 and got["budget"] == {"min": None, "max": None}


# --- end to end ---

def test_predict_negations_hold(client, monkeypatch):
    cat = get_catalogue().set_index(["model", "variant"], drop=False)

    data = predict(client, monkeypatch, "SUV without sunroof, not Mahindra")
    assert data["recommendations"]
    for car in data["recommendations"]:
        row = cat.loc[(car["Model"], car["Variant"])]
        assert row["make"] != "Mahindra"
        assert row["sunroof"] is not True or "sunroof" in row["unverified_fields"]

    data = predict(client, monkeypatch, "CNG car with at most 26 km/kg")
    for car in data["recommendations"]:
        row = cat.loc[(car["Model"], car["Variant"])]
        assert row["fuel_type"] == "cng" and (pd.isna(row["mileage_km_per_kg"]) or row["mileage_km_per_kg"] <= 26)


def test_predict_exclusions_can_be_dropped(client, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "kb")
    data = client.post("/predict", json={"query": "no Tata, no sunroof, 5 lakh tak hatchback",
                                         "drop": ["exclude_make"]}).get_json()
    assert data["dropped"] == [{"key": "exclude_make", "label": "excluding Tata"}]
    drop_sunroof = client.post("/predict", json={"query": "no Tata, no sunroof, 5 lakh tak hatchback",
                                                 "drop": ["exclude_feature:sunroof"]}).get_json()
    assert drop_sunroof["dropped"] == [{"key": "exclude_feature:sunroof", "label": "no sunroof"}]


# --- (d) unsupported-only and vague ---

def test_unsupported_brand_only_returns_no_cars_and_a_message(client, monkeypatch):
    data = predict(client, monkeypatch, "Mini Cooper")
    assert data["recommendations"] == []
    assert "Mini" in data["message"] and "catalogue" in data["message"]
    assert data["unsupported_terms"] == ["Mini"]
    assert data["vague"] is False


def test_unsupported_brand_with_other_content_still_ranks(client, monkeypatch):
    data = predict(client, monkeypatch, "BMW SUV")
    assert data["recommendations"] and "BMW" in data["message"]


def test_vague_query_is_flagged_and_still_returns_the_default_list(client, monkeypatch):
    data = predict(client, monkeypatch, "good car")
    assert data["vague"] is True
    assert data["recommendations"]
    assert "budget" in data["message"]
    specific = predict(client, monkeypatch, "petrol hatchback under 8 lakh")
    assert specific["vague"] is False
