import math

import pandas as pd
import pytest

from services.catalogue import get_catalogue
from services.filter_v2 import (
    AUTOMATIC_TYPES, UNRATED_SAFETY_LABEL, allowed_transmission_types, filter_candidates,
)
from services.ranking_adapter import rank_candidates

NAN = math.nan


def intent(**fields):
    base = {
        "budget": {"min": None, "max": None}, "body_types": [], "fuel_types": [],
        "exclude_body_types": [], "exclude_fuel_types": [],
        "transmission": {"family": None, "include_types": [], "exclude_types": []},
        "seats_min": None, "makes": [], "models": [], "required_features": [],
        "min_airbags": None, "min_safety_stars": None, "min_boot_space_litres": None,
        "min_ground_clearance_mm": None, "min_ev_range_km": None, "min_mileage_kmpl": None,
        "use_case": None, "soft_preferences": [],
    }
    base.update(fields)
    return base


def frame(*overrides):
    """Synthetic catalogue rows: a real petrol row with per-row overrides; index = variant_id."""
    template = get_catalogue().loc[1].to_dict()
    rows = []
    for i, o in enumerate(overrides, start=1):
        row = dict(template, variant_id=i, model=f"M{i}", unverified_fields=frozenset())
        row.update(o)
        rows.append(row)
    df = pd.DataFrame(rows)
    df.index = df["variant_id"].to_numpy()
    return df


def ids(df):
    return sorted(df["variant_id"].tolist())


# --- tri-state required features ---

def test_feature_tristate():
    df = frame({"sunroof": True}, {"sunroof": None, "unverified_fields": frozenset({"sunroof"})}, {"sunroof": False})
    out = filter_candidates(intent(required_features=["sunroof"]), df)
    assert ids(out) == [1, 2]
    assert out.loc[1, "matched"] == ["sunroof"] and out.loc[1, "unverified"] == []
    assert out.loc[2, "unverified"] == ["Unverified: sunroof"] and out.loc[2, "n_soft_flags"] == 1


def test_adas_feature_uses_adas_available():
    df = frame({"adas_available": True, "adas_tier": 0.0}, {"adas_available": False, "adas_tier": 1.0})
    assert ids(filter_candidates(intent(required_features=["adas"]), df)) == [1]


# --- tri-state minimums ---

def test_min_tristate():
    df = frame({"airbags": 6.0}, {"airbags": NAN, "unverified_fields": frozenset({"airbags"})}, {"airbags": 2.0})
    out = filter_candidates(intent(min_airbags=6), df)
    assert ids(out) == [1, 2]
    assert out.loc[1, "matched"] == ["min_airbags"]
    assert out.loc[2, "unverified"] == ["Unverified: airbags"]


def test_min_not_applicable_is_excluded():
    # petrol car: ev_range_km blank and NOT in unverified_fields -> not applicable -> excluded
    df = frame({"ev_range_km": NAN},
               {"fuel_type": "electric", "ev_range_km": 450.0},
               {"fuel_type": "electric", "ev_range_km": NAN, "unverified_fields": frozenset({"ev_range_km"})})
    out = filter_candidates(intent(min_ev_range_km=400), df)
    assert ids(out) == [2, 3]
    assert out.loc[3, "unverified"] == ["Unverified: EV range"]


def test_mileage_cng_falls_back_to_km_per_kg():
    df = frame({"fuel_type": "cng", "mileage_kmpl": NAN, "mileage_km_per_kg": 30.0},
               {"fuel_type": "cng", "mileage_kmpl": NAN, "mileage_km_per_kg": 15.0},
               {"fuel_type": "electric", "mileage_kmpl": NAN},
               {"mileage_kmpl": 21.0}, {"mileage_kmpl": 15.0})
    assert ids(filter_candidates(intent(min_mileage_kmpl=20), df)) == [1, 4]


# --- safety ---

def test_safety_rated_unrated():
    df = frame({"safety_stars_adult": 5.0}, {"safety_stars_adult": 3.0}, {"safety_stars_adult": NAN})
    out = filter_candidates(intent(min_safety_stars=4), df)
    assert ids(out) == [1, 3]
    assert not out.loc[1, "unrated_safety"] and out.loc[1, "matched"] == ["min_safety_stars"]
    assert out.loc[3, "unrated_safety"] and out.loc[3, "n_soft_flags"] == 1
    assert UNRATED_SAFETY_LABEL == "No Bharat NCAP rating on record"


def test_unrated_safety_ignored_without_safety_constraint():
    out = filter_candidates(intent(), frame({"safety_stars_adult": NAN}))
    assert not out.loc[1, "unrated_safety"] and out.loc[1, "n_soft_flags"] == 0


# --- transmission sets ---

@pytest.mark.parametrize("transmission,want", [
    ({"family": "automatic", "include_types": [], "exclude_types": []}, set(AUTOMATIC_TYPES)),
    ({"family": "manual", "include_types": [], "exclude_types": []}, {"manual", "imt"}),
    ({"family": "automatic", "include_types": ["amt"], "exclude_types": []}, {"amt"}),
    ({"family": "automatic", "include_types": ["cvt", "e_cvt"], "exclude_types": []}, {"cvt", "e_cvt"}),
    ({"family": "automatic", "include_types": [], "exclude_types": ["amt"]}, set(AUTOMATIC_TYPES) - {"amt"}),
    ({"family": "manual", "include_types": ["imt"], "exclude_types": []}, {"imt"}),
    ({"family": None, "include_types": [], "exclude_types": ["imt"]}, set(AUTOMATIC_TYPES) | {"manual"}),
])
def test_transmission_sets(transmission, want):
    assert allowed_transmission_types(transmission) == want


def test_transmission_filter_on_rows():
    df = frame(*({"transmission_type": t} for t in ["manual", "imt", "amt", "dct", "single_speed_ev"]))
    auto_no_amt = {"family": "automatic", "include_types": [], "exclude_types": ["amt"]}
    assert ids(filter_candidates(intent(transmission=auto_no_amt), df)) == [4, 5]
    manual = {"family": "manual", "include_types": [], "exclude_types": []}
    assert ids(filter_candidates(intent(transmission=manual), df)) == [1, 2]


# --- exclusions, seats, makes/models, budget ---

def test_body_and_fuel_exclusions():
    df = frame({"body_type": "suv", "fuel_type": "diesel"}, {"body_type": "suv", "fuel_type": "petrol"},
               {"body_type": "sedan", "fuel_type": "petrol"})
    assert ids(filter_candidates(intent(exclude_fuel_types=["diesel"]), df)) == [2, 3]
    assert ids(filter_candidates(intent(exclude_body_types=["suv"]), df)) == [3]
    assert ids(filter_candidates(intent(body_types=["suv"], exclude_fuel_types=["diesel"]), df)) == [2]


def test_seats_is_at_least():
    df = frame({"seats": 5.0}, {"seats": 7.0}, {"seats": 8.0})
    assert ids(filter_candidates(intent(seats_min=7), df)) == [2, 3]


def test_makes_and_models():
    df = frame({"make": "Hyundai", "model": "Creta"}, {"make": "Hyundai", "model": "Venue"},
               {"make": "Tata", "model": "Nexon"}, {"make": "Kia", "model": "Seltos"})
    assert ids(filter_candidates(intent(makes=["Hyundai"], models=["Creta"]), df)) == [1]
    assert ids(filter_candidates(intent(makes=["Tata"], models=["Creta"]), df)) == [1, 3]
    assert ids(filter_candidates(intent(makes=["Hyundai"]), df)) == [1, 2]


def test_budget_range():
    df = frame({"price_ex_showroom": 700_000.0}, {"price_ex_showroom": 1_000_000.0}, {"price_ex_showroom": 1_300_000.0})
    assert ids(filter_candidates(intent(budget={"min": 800_000, "max": 1_200_000}), df)) == [2]


# --- ordering ---

def test_order_soft_flags_before_score():
    # row 2 would score higher (cheaper/better mileage), but carries an unverified flag
    df = frame({"sunroof": True, "mileage_kmpl": 12.0},
               {"sunroof": None, "unverified_fields": frozenset({"sunroof"}), "mileage_kmpl": 25.0})
    it = intent(required_features=["sunroof"])
    ranked, _ = rank_candidates(it, filter_candidates(it, df))
    assert ranked["variant_id"].tolist() == [1, 2]


def test_soft_preference_boost_is_bounded():
    df = frame({"power_bhp": 200.0, "price_ex_showroom": 1_400_000.0}, {"power_bhp": 80.0},
               {"power_bhp": 90.0, "price_ex_showroom": 500_000.0})
    plain, _ = rank_candidates(intent(budget={"min": None, "max": 1_500_000}), filter_candidates(intent(), df))
    boosted, _ = rank_candidates(intent(budget={"min": None, "max": 1_500_000}, soft_preferences=["performance"]),
                                 filter_candidates(intent(), df))
    spread = plain["ranking_score"].max() - plain["ranking_score"].min()
    delta = boosted["ranking_score"] - plain["ranking_score"].reindex(boosted.index)
    assert delta.loc[1] == pytest.approx(0.10 * spread)
    assert delta.loc[2] == 0 and delta.loc[3] == 0
