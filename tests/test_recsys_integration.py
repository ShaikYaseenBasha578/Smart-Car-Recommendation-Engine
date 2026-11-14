"""v3 handling of vague / unsupported-only / assumed intents, exclusions and upper bounds, and import hygiene."""
import contextlib
import io
import subprocess
import sys
from pathlib import Path

import pytest

from services.catalogue import get_catalogue
from services.recsys import config
from services.recsys.api import VAGUE_LABEL, recommend
from services.recsys.evidence import Evidence

NO_EVIDENCE = Evidence()
ROOT = Path(__file__).resolve().parents[1]


def current_message(query):
    from app import make_json_safe
    from services import new_car_service as ncs
    with contextlib.redirect_stdout(io.StringIO()):
        return ncs.get_kb_recommendations(query, str(ROOT), make_json_safe)["message"]


def test_unsupported_only_returns_no_cars_and_the_current_message():
    r = recommend("Mini Cooper", evidence=NO_EVIDENCE)
    assert r["intent"]["unsupported_only"] and r["recommendations"] == []
    assert r["message"] == current_message("Mini Cooper")
    assert "Mini" in r["message"]


def test_vague_query_gets_prompt_and_labelled_neutral_shortlist():
    r = recommend("good car", evidence=NO_EVIDENCE)
    assert r["vague"] is True and r["personalised"] is False
    assert "budget" in r["message"].lower() and "for" in r["message"].lower() and "not personalised" in r["message"]
    assert len(r["recommendations"]) >= 3
    assert all(c["match_label"] == VAGUE_LABEL and c["personalised"] is False for c in r["recommendations"])
    # neutral default weights: no use-case profile, no multiplier moved
    assert r["weights_profile"]["profile"] == "neutral" and r["weights_profile"]["drivers"] == []
    assert all(w["multiplier"] == 1.0 for w in r["weights"].values())


def test_vague_ignores_weight_overrides():
    r = recommend("good car", weight_overrides={"safety": 4}, evidence=NO_EVIDENCE)
    assert r["weights"]["safety"]["multiplier"] == 1.0


def test_non_vague_query_is_not_flagged():
    r = recommend("suv under 15 lakh", evidence=NO_EVIDENCE)
    assert r["vague"] is False and "personalised" not in r


def _assumed_intent(**assumed):
    base = recommend("budget car under 12 lakh", evidence=NO_EVIDENCE)["intent"]
    return dict(base, assumed={"body_types": [], "fuel_types": [], **assumed})


def test_assumed_is_a_bounded_boost_never_a_filter_and_can_be_dropped():
    plain = recommend("x", intent=_assumed_intent(), evidence=NO_EVIDENCE)
    boosted = recommend("x", intent=_assumed_intent(body_types=["suv"]), evidence=NO_EVIDENCE)
    assert boosted["assumed"] == {"body_types": ["suv"]}
    assert boosted["assumed_options"] == [{"key": "assumed:body_types", "kind": "body_types", "values": ["suv"]}]
    assert boosted["assumed_boost"] == config.ASSUMED_BOOST
    # never a filter: non-SUVs are still in the result set and the filters summary does not mention body type
    assert "body_types" not in boosted["filters"]
    cat = get_catalogue()
    bodies = {cat.loc[c["variant_id"], "body_type"] for c in boosted["recommendations"]}
    assert "suv" in bodies and len(bodies) > 1
    # bounded: no card moves by more than the boost
    base = {c["variant_id"]: c["scores"]["overall"] for c in plain["recommendations"]}
    for c in boosted["recommendations"]:
        if c["variant_id"] in base:
            delta = c["scores"]["overall"] - base[c["variant_id"]]
            assert -1e-9 <= delta <= config.ASSUMED_BOOST + 1e-4
            assert (delta > 1e-6) == bool(c["assumed_match"]) or c["scores"]["overall"] >= 1.0
    assert any(c["assumed_match"] == ["body suv"] for c in boosted["recommendations"])
    # off switch
    off = recommend("x", intent=_assumed_intent(body_types=["suv"]), drop=["assumed:body_types"], evidence=NO_EVIDENCE)
    assert "assumed" not in off and off["dropped"][0]["key"] == "assumed:body_types"
    assert [c["variant_id"] for c in off["recommendations"]] == [c["variant_id"] for c in plain["recommendations"]]


def test_assumed_fuel_matches_are_reported():
    r = recommend("x", intent=_assumed_intent(fuel_types=["diesel"]), evidence=NO_EVIDENCE)
    assert any(c["assumed_match"] == ["fuel diesel"] for c in r["recommendations"])


# ---- exclusions and upper bounds go through filter_v2 on the v3 path

def _row(card):
    return get_catalogue().loc[card["variant_id"]]


def test_exclusions_and_upper_bounds_enforced():
    r = recommend("SUV not tata or mahindra under 12 lakh with no sunroof and mileage under 40 km/kg",
                  evidence=NO_EVIDENCE)
    assert r["intent"]["exclude_makes"] and r["intent"]["exclude_features"] and "relaxation" not in r
    assert r["recommendations"]
    for c in r["recommendations"]:
        row = _row(c)
        assert row["make"] not in r["intent"]["exclude_makes"]
        assert row["sunroof"] is not True
        assert row["mileage_km_per_kg"] != row["mileage_km_per_kg"] or row["mileage_km_per_kg"] <= 40


def test_upper_bound_relaxation_names_the_violation_and_only_true_ones():
    r = recommend("hatchback without sunroof under 6 lakh, ground clearance under 160 mm, no Maruti",
                  evidence=NO_EVIDENCE)
    assert r["relaxation"]["keys"] == ["max_ground_clearance_mm"] and r["relaxation"]["far"] is False
    for c in r["recommendations"]:
        assert [v["constraint"] for v in c["violations"]] == ["max_ground_clearance_mm"]
        assert _row(c)["ground_clearance_mm"] > 160


def test_excluded_make_relaxation_is_named():
    intent = dict(recommend("hatchback under 6 lakh", evidence=NO_EVIDENCE)["intent"],
                  exclude_makes=["Maruti Suzuki", "Tata", "Hyundai", "Renault", "Citroen", "Kia", "Honda", "Toyota",
                                 "Mahindra", "Skoda", "Volkswagen", "Nissan", "MG"])
    r = recommend("x", intent=intent, evidence=NO_EVIDENCE)
    assert r["recommendations"] and "relaxation" in r
    for c in r["recommendations"]:
        row = _row(c)
        names = {v["constraint"] for v in c["violations"]}
        assert ("exclude_makes" in names) == (row["make"] in intent["exclude_makes"])


def test_display_is_sorted_by_overall_descending():
    for q in ["family suv under 15 lakh", "petrol hatchback under 8 lakh", "good car"]:
        s = [c["scores"]["overall"] for c in recommend(q, evidence=NO_EVIDENCE)["recommendations"]]
        assert s == sorted(s, reverse=True)


def test_far_relaxation_is_flagged_in_the_response():
    intent = dict(recommend("suv", evidence=NO_EVIDENCE)["intent"], budget={"min": None, "max": 200000.0},
                  body_types=["van"], fuel_types=["electric"], required_features=["ventilated_seats", "adas", "camera_360", "sunroof"],
                  seats_min=7)
    r = recommend("x", intent=intent, evidence=NO_EVIDENCE)
    if r["recommendations"]:  # depends on the catalogue; when the cumulative fallback fires it must say so
        assert (len(r["relaxation"]["keys"]) > 3) == r["relaxation"]["far"]


# ---- import hygiene

def test_v3_path_does_not_import_the_legacy_ranking_engine():
    code = ("import sys\n"
            "from services.recsys.api import recommend\n"
            "r = recommend('family suv under 15 lakh')\n"
            "assert r['recommendations']\n"
            "assert 'ranking_engine' not in sys.modules, 'ranking_engine imported'\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
