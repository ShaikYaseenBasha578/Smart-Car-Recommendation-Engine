"""Runs the existing ranking_engine over KB catalogue rows, unchanged.

ranking_engine.py scores rows by the legacy processed_dataset.csv column names and a legacy
filters dict. This adapter renames catalogue columns into that shape (LEGACY_COLUMNS), turns
an intent_v2 dict into a legacy filters dict (legacy_filters), and calls rank_cars as-is.

Soft preferences: the engine has a single use_case, not per-preference weights, so each
soft preference that a variant satisfies adds a share of SOFT_BOOST_SHARE (10%) of the
candidate pool's score range. The boost is bounded by that 10% in total.

Final order: n_soft_flags ascending, then score descending, then variant_id.
"""

from __future__ import annotations

import math

import pandas as pd

from ranking_engine import rank_cars

SOFT_BOOST_SHARE = 0.10

BODY_COLUMNS = {
    "suv": "Body_Type_SUV",
    "sedan": "Body_Type_Sedan",
    "hatchback": "Body_Type_Hatchback",
    "mpv": "Body_Type_MPV",
    "van": "Body_Type_Van",
    "pickup": "Body_Type_Pick-up",
}
FUEL_COLUMNS = {
    "petrol": "Fuel_Type_Petrol",
    "diesel": "Fuel_Type_Diesel",
    "cng": "Fuel_Type_CNG",
    "electric": "Fuel_Type_Electric",
    "hybrid": "Fuel_Type_Hybrid",
}
# legacy column read by ranking_engine -> function of a catalogue row
LEGACY_COLUMNS = {
    "Make": lambda r: r["make"],
    "Model": lambda r: r["model"],
    "Variant": lambda r: r["variant"],
    "Ex-Showroom_Price": lambda r: r["price_ex_showroom"],
    # CNG variants without a kmpl figure are scored on their km/kg figure
    "ARAI_Certified_Mileage": lambda r: r["mileage_kmpl"] if not _nan(r["mileage_kmpl"]) or r["fuel_type"] != "cng"
    else r["mileage_km_per_kg"],
    "Displacement": lambda r: r["engine_cc"],
    "Power": lambda r: r["power_bhp"],
    "Torque": lambda r: r["torque_nm"],
    "Seating_Capacity": lambda r: r["seats"],
    "Transmission_Automatic": lambda r: int(r["transmission_family"] == "automatic"),
    "Transmission_Manual": lambda r: int(r["transmission_family"] == "manual"),
    **{col: (lambda r, b=body: int(r["body_type"] == b)) for body, col in BODY_COLUMNS.items()},
    **{col: (lambda r, f=fuel: int(r["fuel_type"] == f)) for fuel, col in FUEL_COLUMNS.items()},
    "Airbags": lambda r: r["airbags"],
    "ABS_(Anti-lock_Braking_System)": lambda r: _flag(r["abs"]),
    "Sunroof": lambda r: _flag(r["sunroof"]),
    "Ventilated_Seats": lambda r: _flag(r["ventilated_front_seats"]),
    "Cruise_Control": lambda r: _flag(r["cruise_control"]),
    "Android_Auto": lambda r: _flag(r["android_auto"]),
    "Apple_CarPlay": lambda r: _flag(r["apple_carplay"]),
}
# intent feature -> legacy filter key scored by ranking_engine.feature_match_score
LEGACY_FEATURE_FILTERS = {
    "sunroof": "Sunroof",
    "ventilated_seats": "Ventilated_Seats",
    "cruise_control": "Cruise_Control",
    "android_auto": "Android_Auto",
    "apple_carplay": "Apple_CarPlay",
}


def _nan(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _flag(value) -> int:
    # unknown (None) scores like "absent"; the filter has already labelled it unverified
    return 1 if value is True else 0


def to_legacy_frame(candidates: pd.DataFrame) -> pd.DataFrame:
    rows = [{col: fn(r) for col, fn in LEGACY_COLUMNS.items()} for _, r in candidates.iterrows()]
    frame = pd.DataFrame(rows, index=candidates.index, columns=list(LEGACY_COLUMNS))
    frame["variant_id"] = candidates["variant_id"].values
    return frame


def legacy_filters(intent: dict) -> dict:
    filters = {}
    budget = intent.get("budget") or {}
    lo, hi = budget.get("min"), budget.get("max")
    if lo is not None and hi is not None:
        filters["Ex-Showroom_Price"] = [lo, hi]
    elif hi is not None:
        filters["Ex-Showroom_Price"] = hi
    elif lo is not None:
        filters["price_min_only"] = lo

    if intent.get("makes"):
        filters["Make"] = list(intent["makes"])
    if len(intent.get("body_types") or []) == 1:
        filters["Body_Type"] = BODY_COLUMNS[intent["body_types"][0]]
    for fuel in intent.get("fuel_types") or []:
        filters[FUEL_COLUMNS[fuel]] = 1

    family = (intent.get("transmission") or {}).get("family")
    if family == "automatic":
        filters["Transmission_Automatic"] = 1
    elif family == "manual":
        filters["Transmission_Manual"] = 1

    if intent.get("seats_min") is not None:
        filters["Seating_Capacity"] = intent["seats_min"]
    if intent.get("min_mileage_kmpl") is not None:
        filters["ARAI_Certified_Mileage"] = [intent["min_mileage_kmpl"], float("inf")]
    for feature in intent.get("required_features") or []:
        if feature in LEGACY_FEATURE_FILTERS:
            filters[LEGACY_FEATURE_FILTERS[feature]] = 1
    if intent.get("min_airbags") is not None:
        filters["Airbags"] = 1
    return filters


def _soft_hits(row, prefs: list[str]) -> list[str]:
    def num(col):
        v = row[col]
        return None if _nan(v) else v

    checks = {
        "mileage": lambda: (num("mileage_kmpl") or 0) >= 18 or (num("mileage_km_per_kg") or 0) >= 25
        or row["fuel_type"] == "electric",
        "space": lambda: (num("seats") or 0) >= 7 or (num("boot_space_litres") or 0) >= 400,
        "performance": lambda: (num("power_bhp") or 0) >= 120,
        "comfort": lambda: row["ventilated_front_seats"] is True or row["cruise_control"] is True,
        "safety": lambda: (num("safety_stars_adult") or 0) >= 5 or row["adas_available"] is True,
        "features": lambda: sum(row[c] is True for c in (
            "sunroof", "adas_available", "camera_360", "ventilated_front_seats", "cruise_control",
            "wireless_charging", "heads_up_display", "android_auto", "apple_carplay")) >= 6,
    }
    return [p for p in prefs if checks[p]()]


def rank_candidates(intent: dict, candidates: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Candidates with ranking_score / match_reasons, sorted; plus the legacy filters used."""
    filters = legacy_filters(intent)
    if candidates.empty:
        return candidates.assign(ranking_score=[], match_reasons=[]), filters

    ranked = rank_cars(
        filtered_df=to_legacy_frame(candidates),
        filters=filters,
        intent={"use_case": intent.get("use_case")},
        top_n=len(candidates),
    )
    out = candidates.join(ranked[["ranking_score", "match_reasons"]])

    prefs = intent.get("soft_preferences") or []
    if prefs:
        spread = out["ranking_score"].max() - out["ranking_score"].min()
        boost_unit = SOFT_BOOST_SHARE * (spread if spread > 0 else 1) / len(prefs)
        hits = [_soft_hits(r, prefs) for _, r in out.iterrows()]
        out["ranking_score"] = out["ranking_score"] + [boost_unit * len(h) for h in hits]
        out["match_reasons"] = [
            reasons + [f"fits your {p} preference" for p in h]
            for reasons, h in zip(out["match_reasons"], hits)
        ]

    out = out.sort_values(["n_soft_flags", "ranking_score", "variant_id"], ascending=[True, False, True])
    return out, filters
