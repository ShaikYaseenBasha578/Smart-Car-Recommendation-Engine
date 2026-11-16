import json

import numpy as np
import pytest

from services.catalogue import get_catalogue
from services.filter_v2 import AUTOMATIC_TYPES, MANUAL_TYPES
from services.recsys import config
from services.recsys.api import recommend
from services.recsys.evidence import Evidence

CARD_KEYS = {
    "Make", "Model", "Variant", "Ex-Showroom_Price", "Displacement", "Power", "ARAI_Certified_Mileage",
    "Transmission", "Fuel_Type", "carImage", "carDekhoLink", "carWaleLink", "ranking_score", "match_reasons",
    "transmission_type", "transmission_label", "matched_features", "unverified", "safety", "imageAttribution",
    "matching_variant_count", "mileage_km_per_kg", "ev_range_km", "power_bhp", "airbags", "boot_space_litres",
}
V3_CARD_KEYS = {"scores", "reasons", "unknowns", "violations", "match_label", "variant_id", "criteria", "flags"}
TOP_KEYS = {"engine", "parser_used", "intent", "filters", "recommendations", "data_as_of", "unsupported_terms",
            "covered_makes", "weights"}
NO_EVIDENCE = Evidence()

QUERIES = [
    "family suv under 15 lakh with sunroof",
    "best petrol hatchback under 8 lakh",
    "10 lakh ke andar automatic gaadi mileage achha",
    "7 seater diesel suv under 6 lakh with sunroof and adas",      # over-constrained
    "electric car under 20 lakh",
    "cng sedan",
    "something like Creta with ventilated seats",                   # required feature, unknown for some cars
    "safe car for my parents around 12 lakh no diesel",
    "highway cruiser automatic suv above 20 lakh",
    "tata cars with cruise control under 12 lakh",
]


def violates(card, intent):
    """independent check of the hard constraints against the catalogue row"""
    row = get_catalogue().loc[card["variant_id"]]
    b = intent["budget"]
    out = []
    if b.get("max") is not None and row["price_ex_showroom"] > b["max"]:
        out.append("budget max")
    if b.get("min") is not None and row["price_ex_showroom"] < b["min"]:
        out.append("budget min")
    if intent["body_types"] and row["body_type"] not in intent["body_types"]:
        out.append("body")
    if row["body_type"] in intent["exclude_body_types"]:
        out.append("exclude body")
    if intent["fuel_types"] and row["fuel_type"] not in intent["fuel_types"]:
        out.append("fuel")
    if row["fuel_type"] in intent["exclude_fuel_types"]:
        out.append("exclude fuel")
    if intent["seats_min"] is not None and row["seats"] < intent["seats_min"]:
        out.append("seats")
    if intent["makes"] and not (row["make"] in intent["makes"] or row["model"] in intent["models"]):
        out.append("make")
    fam = intent["transmission"]["family"]
    if fam == "automatic" and row["transmission_type"] not in AUTOMATIC_TYPES:
        out.append("automatic")
    if fam == "manual" and row["transmission_type"] not in MANUAL_TYPES:
        out.append("manual")
    cols = {"sunroof": "sunroof", "adas": "adas_available", "ventilated_seats": "ventilated_front_seats",
            "cruise_control": "cruise_control", "camera_360": "camera_360"}
    for f in intent["required_features"]:
        if row[cols[f]] is False:
            out.append(f"feature {f}")
    return out


@pytest.fixture(scope="module")
def responses():
    return {q: recommend(q, evidence=NO_EVIDENCE) for q in QUERIES}


def test_required_keys_and_json(responses):
    for q, r in responses.items():
        assert TOP_KEYS <= set(r), q
        assert r["engine"] == "v3"
        json.dumps(r, allow_nan=False)   # no NaN / numpy leaks
        for c in r["recommendations"]:
            assert CARD_KEYS <= set(c) and V3_CARD_KEYS <= set(c), q
            assert set(c["scores"]) == {"overall", "spec", "expert", "owner", "coverage"}
            assert len(c["reasons"]) <= config.MAX_REASONS
        assert all({"weight", "label"} <= set(w) for w in r["weights"].values())
        assert len(r["recommendations"]) <= config.MAX_MODELS + 4


def test_card_keys_match_the_current_predict_cards():
    """the v3 card carries every key the kb path's card has"""
    import re
    src = open("services/new_car_service.py", encoding="utf-8").read()
    kb = src[src.index("def get_kb_recommendations"):src.index("def get_legacy_recommendations")]
    old_keys = set(re.findall(r'^\s+"([A-Za-z_\-]+)":', kb[kb.index("recommendations.append"):], re.M))
    card = recommend("family suv under 15 lakh", evidence=NO_EVIDENCE)["recommendations"][0]
    assert old_keys - {"scores"} <= set(card), old_keys - set(card)


def test_no_hard_constraint_violated_unless_relaxed(responses):
    for q, r in responses.items():
        for c in r["recommendations"]:
            if "relaxation" in r:
                assert c["violations"] or not violates(c, r["intent"]), q
                declared = {v["constraint"] for v in c["violations"]}
                assert declared <= set(r["relaxation"]["keys"])
            else:
                assert violates(c, r["intent"]) == [], (q, c["Model"])
                assert c["violations"] == []


def test_relaxed_response_names_what_was_relaxed(responses):
    r = responses["7 seater diesel suv under 6 lakh with sunroof and adas"]
    assert "relaxation" in r and r["relaxation"]["moves"] \
        and ("No cars match" in r["message"] or r["message"].startswith("No car is confirmed to have all of:"))
    assert r["recommendations"] and all(c["violations"] for c in r["recommendations"])
    assert all(v["text"] for c in r["recommendations"] for v in c["violations"])


def test_one_card_per_model(responses):
    for r in responses.values():
        models = [(c["Make"], c["Model"]) for c in r["recommendations"]]
        assert len(models) == len(set(models))


def test_unknown_required_feature_kept_flagged(responses):
    r = responses["something like Creta with ventilated seats"]
    flagged = [c for c in r["recommendations"] if "unknown_required:feature:ventilated_seats" in c["flags"]]
    for c in flagged:
        assert any("Ventilated seats" in u for u in c["unknowns"])


def test_best_variant_not_lowest_id():
    r = recommend("suv under 20 lakh", evidence=NO_EVIDENCE)
    df = get_catalogue()
    lowest = df[df["model"].isin([c["Model"] for c in r["recommendations"]])].groupby("model")["variant_id"].min()
    assert any(c["variant_id"] != lowest[c["Model"]] for c in r["recommendations"])


def test_deterministic():
    a = recommend("family suv under 15 lakh with sunroof", evidence=NO_EVIDENCE)
    b = recommend("family suv under 15 lakh with sunroof", evidence=NO_EVIDENCE)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_weight_overrides_and_drop():
    base = recommend("family suv under 15 lakh", evidence=NO_EVIDENCE)
    off = recommend("family suv under 15 lakh", weight_overrides={"safety": False}, evidence=NO_EVIDENCE)
    assert base["weights"]["safety"]["weight"] > 0 and off["weights"]["safety"]["weight"] == 0
    assert off["weights"]["safety"]["active"] is False
    dropped = recommend("suv under 6 lakh with sunroof", drop=["budget"], evidence=NO_EVIDENCE)
    assert dropped["dropped"][0]["key"] == "budget" and dropped["recommendations"]


def test_empty_result_when_nothing_possible():
    r = recommend("anything", intent=dict(recommend("suv", evidence=NO_EVIDENCE)["intent"], budget={"min": None, "max": 10}),
                  evidence=NO_EVIDENCE)
    # relaxation can drop the budget entirely, so cars come back and are named
    assert r["recommendations"] and "relaxation" in r


def test_empty_evidence_files_do_not_change_the_cards(tmp_path):
    from services.recsys.evidence import (ASSESSMENT_COLS, OWNER_COLS, OWNER_RATING_COLS, REVIEW_ASSESSMENT_COLS)
    for name, cols in (("a.csv", REVIEW_ASSESSMENT_COLS), ("t.csv", OWNER_COLS), ("r.csv", OWNER_RATING_COLS),
                       ("legacy.csv", ASSESSMENT_COLS)):
        (tmp_path / name).write_text(",".join(cols) + "\n")
    a = recommend("family suv under 15 lakh", evidence=NO_EVIDENCE)
    # header-only files in both assessment layouts (the repo files now hold the KB review export)
    for assess in ("a.csv", "legacy.csv"):
        b = recommend("family suv under 15 lakh",
                      evidence=Evidence.load(tmp_path / assess, tmp_path / "t.csv", tmp_path / "r.csv"))
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    b = recommend("family suv under 15 lakh", evidence=Evidence.load(tmp_path / "a.csv", tmp_path / "t.csv", tmp_path / "r.csv"))
    assert [c["variant_id"] for c in a["recommendations"]] == [c["variant_id"] for c in b["recommendations"]]
