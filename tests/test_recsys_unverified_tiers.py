"""Blank handling 2026-11-15, change 2: a blank cannot quietly pass a requirement.

A car that passes a requirement only because the field is unknown ("unknown kept") ranks below every car that has it
verified (tier = number of unverified requirements, score order inside a tier) and carries a label naming the field."""
import numpy as np
import pytest

from services.catalogue import get_catalogue
from services.intent_v2 import parse_intent
from services.recsys.api import recommend
from services.recsys.diversify import diversify, displayed_variant_per_model
from services.recsys.evidence import Evidence
from services.recsys.score import score_candidates
from tests.recsys_frames import make_frame

NO_EVIDENCE = Evidence()
GC_UNVERIFIED = frozenset({"ground_clearance_mm"})


def run(query, rows):
    return recommend(query, evidence=NO_EVIDENCE, catalogue=make_frame(rows), intent=parse_intent(query))["recommendations"]


def order(cards):
    return [c["Model"] for c in cards]


def gc_rows():
    """Verified cars are modest (low power); the unverified ones are the strongest on paper."""
    rows = [dict(model=f"V{i}", ground_clearance_mm=210.0 + 5 * i, power_bhp=70 + 2 * i) for i in range(3)]
    rows += [dict(model=f"U{i}", ground_clearance_mm=np.nan, unverified_fields=GC_UNVERIFIED, power_bhp=160 + 10 * i,
                  sunroof=True, adas_available=True, camera_360=True) for i in range(3)]
    rows += [dict(model="LOW", ground_clearance_mm=170.0, power_bhp=200.0)]       # known below: not a candidate
    return rows


def test_ground_clearance_verified_cars_rank_above_every_unknown_one_and_unknown_ones_are_labelled():
    cards = run("SUV with ground clearance of at least 210 mm", gc_rows())
    assert order(cards)[:3] == ["V2", "V1", "V0"] or set(order(cards)[:3]) == {"V0", "V1", "V2"}
    assert set(order(cards)[3:]) == {"U0", "U1", "U2"} and "LOW" not in order(cards)
    for c in cards[:3]:
        assert c["not_verified"] == []
    for c in cards[3:]:
        assert c["not_verified"] == ["ground clearance not verified"]
        assert any(u.startswith("Ground clearance: not confirmed") for u in c["unknowns"])
    # without the tiers the unverified cars would win on score: this is the point of the rule
    assert min(c["ranking_score"] for c in cards[3:]) > max(c["ranking_score"] for c in cards[:3])


def test_score_order_is_kept_inside_each_tier():
    cards = run("SUV with ground clearance of at least 210 mm", gc_rows())
    for tier in (cards[:3], cards[3:]):
        scores = [c["ranking_score"] for c in tier]
        assert scores == sorted(scores, reverse=True)


def test_selection_fills_from_the_verified_tier_first():
    """Twelve candidates but eight slots: all eight shown must come from the verified tier when it has eight."""
    rows = [dict(model=f"V{i}", ground_clearance_mm=215.0, power_bhp=70 + i) for i in range(8)]
    rows += [dict(model=f"U{i}", ground_clearance_mm=np.nan, unverified_fields=GC_UNVERIFIED, power_bhp=200 + i,
                  sunroof=True, adas_available=True) for i in range(4)]
    cards = run("SUV with ground clearance of at least 210 mm", rows)
    assert sorted(order(cards)) == sorted(f"V{i}" for i in range(8))


def test_variant_with_the_requirement_verified_is_shown_for_a_model_that_has_both():
    rows = [dict(model="A", variant="unknown-top", ground_clearance_mm=np.nan, unverified_fields=GC_UNVERIFIED,
                 power_bhp=180.0, sunroof=True, adas_available=True, price_ex_showroom=1500000.0),
            dict(model="A", variant="known-base", ground_clearance_mm=220.0, power_bhp=90.0)]
    cards = run("SUV with ground clearance of at least 210 mm", rows)
    assert [c["Variant"] for c in cards] == ["known-base"] and cards[0]["not_verified"] == []


def test_two_requirements_tier_by_the_number_unverified():
    rows = [dict(model="BOTH_UNKNOWN", sunroof=None, unverified_fields=frozenset({"sunroof", "ground_clearance_mm"}),
                 ground_clearance_mm=np.nan, power_bhp=250.0, adas_available=True, camera_360=True),
            dict(model="ONE_UNKNOWN", sunroof=True, ground_clearance_mm=np.nan, unverified_fields=GC_UNVERIFIED,
                 power_bhp=180.0, adas_available=True),
            dict(model="VERIFIED", sunroof=True, ground_clearance_mm=212.0, power_bhp=75.0)]
    cards = run("SUV with sunroof and ground clearance of at least 210 mm", rows)
    assert order(cards) == ["VERIFIED", "ONE_UNKNOWN", "BOTH_UNKNOWN"]
    assert [len(c["not_verified"]) for c in cards] == [0, 1, 2]
    assert set(cards[2]["not_verified"]) == {"sunroof not verified", "ground clearance not verified"}


def test_no_sunroof_known_absent_ranks_above_blank_and_the_blank_names_the_absence():
    rows = [dict(model="KNOWN_NO", sunroof=False, power_bhp=75.0),
            dict(model="BLANK_A", sunroof=None, power_bhp=190.0, adas_available=True, camera_360=True),
            dict(model="BLANK_B", sunroof=None, power_bhp=170.0, adas_available=True),
            dict(model="HAS_ONE", sunroof=True, power_bhp=250.0)]          # known present: excluded
    cards = run("no sunroof", rows)
    assert order(cards)[0] == "KNOWN_NO" and set(order(cards)[1:]) == {"BLANK_A", "BLANK_B"}
    assert all(c["not_verified"] == ["sunroof absence not verified"] for c in cards[1:])
    assert cards[0]["not_verified"] == []


def test_mileage_minimum_unknown_kept_and_labelled():
    rows = [dict(model="KNOWN", body_type="hatchback", mileage_kmpl=23.5, power_bhp=70.0),
            dict(model="BLANK", body_type="hatchback", mileage_kmpl=np.nan, unverified_fields=frozenset({"mileage_kmpl"}),
                 power_bhp=120.0, adas_available=True),
            dict(model="SLOW", body_type="hatchback", mileage_kmpl=15.0, power_bhp=150.0)]
    cards = run("petrol hatchback with mileage above 22 kmpl", rows)
    assert order(cards) == ["KNOWN", "BLANK"]
    assert cards[1]["not_verified"] == ["mileage not verified"] and cards[0]["not_verified"] == []


def test_without_requirements_nothing_changes():
    rows = [dict(model=f"M{i}", power_bhp=80 + 10 * i, ground_clearance_mm=np.nan if i % 2 else 200.0) for i in range(6)]
    cards = run("SUV", rows)
    assert all(c["not_verified"] == [] for c in cards)
    scores = [c["ranking_score"] for c in cards]
    assert scores == sorted(scores, reverse=True)


def test_diversify_tiers_hand_frame():
    df = make_frame([dict(model="A"), dict(model="B"), dict(model="C")])
    df["overall"] = [0.9, 0.8, 0.7]
    df["n_soft_flags"] = [1, 0, 2]
    assert [r["model"] for r in diversify(df, {})] == ["B", "A", "C"]
    assert list(displayed_variant_per_model(df)["model"]) == ["B", "A", "C"]


@pytest.mark.parametrize("query", ["SUV with ground clearance of at least 210 mm",
                                   "petrol hatchback with mileage above 22 kmpl", "no sunroof"])
def test_real_catalogue_tiers_are_monotone_and_every_unverified_car_is_labelled(query):
    cards = recommend(query, evidence=NO_EVIDENCE)["recommendations"]
    assert cards
    tiers = [len(c["not_verified"]) for c in cards]
    assert tiers == sorted(tiers)                                  # fewest unverified requirements first
    for t in set(tiers):
        scores = [c["ranking_score"] for c in cards if len(c["not_verified"]) == t]
        assert scores == sorted(scores, reverse=True)
    for c in cards:
        if c["unverified"]:
            assert c["not_verified"], c["Model"]
