"""Read-only access to the KB catalogue export (data/catalogue.csv + catalogue_meta.json).

Loaded once at import. Booleans are True/False/None (None = unknown), numbers are float
(NaN = unknown), unverified_fields is a set of column names.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CATALOGUE_CSV = DATA_DIR / "catalogue.csv"
META_JSON = DATA_DIR / "catalogue_meta.json"

TEXT_COLUMNS = [
    "make", "model", "variant", "full_name", "body_type", "fuel_raw", "fuel_type",
    "transmission_raw", "transmission_type", "transmission_family", "drivetrain",
    "safety_testing_body",
]
NUMERIC_COLUMNS = [
    "price_ex_showroom", "seats", "engine_cc", "power_bhp", "torque_nm", "mileage_kmpl",
    "mileage_km_per_kg", "ev_range_km", "boot_space_litres", "ground_clearance_mm", "airbags",
    "adas_tier", "safety_stars_adult", "safety_stars_child", "safety_test_year",
]
BOOL_COLUMNS = [
    "abs", "android_auto", "apple_carplay", "cruise_control", "sunroof", "adas_available",
    "camera_360", "ventilated_front_seats", "wireless_charging", "heads_up_display",
]
_BOOL_VALUES = {"true": True, "false": False, "": None}


def _load_catalogue() -> pd.DataFrame:
    dtypes = {"variant_id": "int64", "unverified_fields": "string"}
    dtypes.update({c: "string" for c in TEXT_COLUMNS + BOOL_COLUMNS})
    dtypes.update({c: "float64" for c in NUMERIC_COLUMNS})
    df = pd.read_csv(CATALOGUE_CSV, dtype=dtypes, keep_default_na=False, na_values={c: [""] for c in NUMERIC_COLUMNS})

    for col in BOOL_COLUMNS:
        unknown = set(df[col].unique()) - set(_BOOL_VALUES)
        if unknown:
            raise ValueError(f"catalogue.csv: unexpected {col} values {sorted(unknown)}")
        df[col] = df[col].map(_BOOL_VALUES).astype(object)
    for col in TEXT_COLUMNS:
        df[col] = df[col].astype(object).where(df[col] != "", None)
    df["unverified_fields"] = [frozenset(v.split(";")) if v else frozenset() for v in df["unverified_fields"]]

    if df["variant_id"].duplicated().any():
        raise ValueError("catalogue.csv: duplicate variant_id")
    df.index = df["variant_id"].to_numpy()  # unnamed, so "variant_id" stays unambiguous as a column
    return df


_CATALOGUE = _load_catalogue()
_META = json.loads(META_JSON.read_text(encoding="utf-8"))


def get_catalogue() -> pd.DataFrame:
    """The shared catalogue frame. Treat as read-only; copy before mutating."""
    return _CATALOGUE


def get_meta() -> dict:
    return _META
