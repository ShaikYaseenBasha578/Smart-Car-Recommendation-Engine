"""Hard filters + tri-state constraint matching over the KB catalogue.

Hard filters (row must satisfy): budget, body include/exclude, fuel include/exclude,
transmission, seats_min (>=), makes, models.

Tri-state (required_features and every min_* constraint):
  meets                     -> matched
  null / unverified         -> kept, labelled "Unverified: <label>"
  known false / below       -> excluded
A blank in a field that does not apply to the fuel type (e.g. ev_range_km on a petrol car,
mileage on an EV) is "not applicable", not unverified: such a row cannot meet that minimum
and is excluded.

Mileage: min_mileage_kmpl is checked against mileage_kmpl. A CNG variant with no kmpl figure
falls back to mileage_km_per_kg (its ARAI figure is quoted per kg).

min_safety_stars: rated and meets -> matched; rated below -> excluded; unrated -> kept with
unrated_safety=True ("No Bharat NCAP rating on record").

reference_models ("something like Creta"): the reference model itself is excluded, and unless
the user gave a budget, price must sit in [0.8 x its cheapest, 1.2 x its dearest variant].
(intent_v2 already sets body_types to the reference model's body type.) If the reference's
length is known, length_mm must also sit within +/-8% of its median length (per reference
model; the band spans all of them). A candidate with unknown length is kept, flagged
length_unknown, and ranked after length-confirmed ones. Unknown reference length: no length band.
"""

from __future__ import annotations

import math

import pandas as pd

AUTOMATIC_TYPES = ["amt", "dct", "cvt", "e_cvt", "torque_converter", "single_speed_ev"]
MANUAL_TYPES = ["manual", "imt"]

# intent feature -> (catalogue column, human label)
FEATURE_COLUMNS = {
    "sunroof": ("sunroof", "sunroof"),
    "adas": ("adas_available", "ADAS"),
    "camera_360": ("camera_360", "360° camera"),
    "ventilated_seats": ("ventilated_front_seats", "ventilated seats"),
    "cruise_control": ("cruise_control", "cruise control"),
    "wireless_charging": ("wireless_charging", "wireless charging"),
    "heads_up_display": ("heads_up_display", "heads-up display"),
    "android_auto": ("android_auto", "Android Auto"),
    "apple_carplay": ("apple_carplay", "Apple CarPlay"),
}
# intent min_* -> (catalogue column, human label)
MIN_COLUMNS = {
    "min_airbags": ("airbags", "airbags"),
    "min_boot_space_litres": ("boot_space_litres", "boot space"),
    "min_ground_clearance_mm": ("ground_clearance_mm", "ground clearance"),
    "min_ev_range_km": ("ev_range_km", "EV range"),
    "min_mileage_kmpl": ("mileage_kmpl", "mileage"),
}
UNRATED_SAFETY_LABEL = "No Bharat NCAP rating on record"
REFERENCE_PRICE_BAND = (0.8, 1.2)
REFERENCE_LENGTH_TOLERANCE = 0.08


def reference_price_band(intent: dict, df: pd.DataFrame) -> tuple[float, float] | None:
    """Price band from the reference models, or None if there are none or the user set a budget."""
    budget = intent.get("budget") or {}
    refs = intent.get("reference_models") or []
    if not refs or budget.get("min") is not None or budget.get("max") is not None:
        return None
    prices = df.loc[df["model"].isin(refs), "price_ex_showroom"].dropna()
    if prices.empty:
        return None
    lo, hi = REFERENCE_PRICE_BAND
    return lo * prices.min(), hi * prices.max()


def reference_length_band(intent: dict, df: pd.DataFrame) -> tuple[float, float] | None:
    """+/-8% around the reference models' median length_mm, or None if no reference length is known."""
    refs = intent.get("reference_models") or []
    if not refs:
        return None
    medians = df.loc[df["model"].isin(refs)].groupby("model")["length_mm"].median().dropna()
    if medians.empty:
        return None
    return (1 - REFERENCE_LENGTH_TOLERANCE) * medians.min(), (1 + REFERENCE_LENGTH_TOLERANCE) * medians.max()


def allowed_transmission_types(transmission: dict) -> set[str]:
    include = transmission.get("include_types") or []
    family = transmission.get("family")
    if include:
        allowed = set(include)
    elif family == "automatic":
        allowed = set(AUTOMATIC_TYPES)
    elif family == "manual":
        allowed = set(MANUAL_TYPES)
    else:
        allowed = set(AUTOMATIC_TYPES + MANUAL_TYPES)
    return allowed - set(transmission.get("exclude_types") or [])


def _hard_filter(intent: dict, df: pd.DataFrame) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)

    budget = intent.get("budget") or {}
    if budget.get("min") is not None:
        mask &= df["price_ex_showroom"] >= budget["min"]
    if budget.get("max") is not None:
        mask &= df["price_ex_showroom"] <= budget["max"]

    if intent.get("body_types"):
        mask &= df["body_type"].isin(intent["body_types"])
    if intent.get("exclude_body_types"):
        mask &= ~df["body_type"].isin(intent["exclude_body_types"])
    if intent.get("fuel_types"):
        mask &= df["fuel_type"].isin(intent["fuel_types"])
    if intent.get("exclude_fuel_types"):
        mask &= ~df["fuel_type"].isin(intent["exclude_fuel_types"])

    refs = intent.get("reference_models") or []
    if refs:
        mask &= ~df["model"].isin(refs)
        band = reference_price_band(intent, df)
        if band:
            mask &= df["price_ex_showroom"].between(*band)
        length_band = reference_length_band(intent, df)
        if length_band:
            mask &= df["length_mm"].between(*length_band) | df["length_mm"].isna()

    mask &= df["transmission_type"].isin(allowed_transmission_types(intent.get("transmission") or {}))

    if intent.get("seats_min") is not None:
        mask &= df["seats"] >= intent["seats_min"]

    # "Hyundai Creta" -> only Creta; "Tata or Creta" -> every Tata plus Creta
    models = intent.get("models") or []
    makes = intent.get("makes") or []
    if models or makes:
        model_makes = set(df.loc[df["model"].isin(models), "make"])
        free_makes = [m for m in makes if m not in model_makes]
        mask &= df["model"].isin(models) | df["make"].isin(free_makes)

    return df[mask]


def _check_row(row, intent: dict):
    """(keep, matched, unverified, unrated_safety) for one hard-filtered row."""
    matched, unverified = [], []
    unverified_fields = row["unverified_fields"]

    for feature in intent.get("required_features") or []:
        col, label = FEATURE_COLUMNS[feature]
        value = row[col]
        if value is True and col not in unverified_fields:
            matched.append(feature)
        elif value is None or col in unverified_fields:
            unverified.append(f"Unverified: {label}")
        else:
            return False, [], [], False

    for key, (col, label) in MIN_COLUMNS.items():
        threshold = intent.get(key)
        if threshold is None:
            continue
        value = row[col]
        if key == "min_mileage_kmpl" and _is_nan(value) and row["fuel_type"] == "cng":
            col, value = "mileage_km_per_kg", row["mileage_km_per_kg"]
        if not _is_nan(value):
            if value >= threshold:
                matched.append(key)
                continue
            return False, [], [], False
        if col in unverified_fields:
            unverified.append(f"Unverified: {label}")
            continue
        return False, [], [], False  # blank and not applicable to this fuel type

    unrated_safety = False
    stars = intent.get("min_safety_stars")
    if stars is not None:
        rating = row["safety_stars_adult"]
        if _is_nan(rating):
            unrated_safety = True
        elif rating >= stars:
            matched.append("min_safety_stars")
        else:
            return False, [], [], False

    return True, matched, unverified, unrated_safety


def _is_nan(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def filter_candidates(intent: dict, df: pd.DataFrame) -> pd.DataFrame:
    """Surviving variants, with matched / unverified / unrated_safety / n_soft_flags / length_unknown columns."""
    hard = _hard_filter(intent, df)
    keep, matched, unverified, unrated = [], [], [], []
    for _, row in hard.iterrows():
        ok, m, u, r = _check_row(row, intent)
        keep.append(ok)
        matched.append(m)
        unverified.append(u)
        unrated.append(r)

    out = hard.copy()
    out["matched"] = matched
    out["unverified"] = unverified
    out["unrated_safety"] = unrated
    out = out[pd.Series(keep, index=out.index, dtype=bool)].copy()
    out["n_soft_flags"] = out["unverified"].map(len) + out["unrated_safety"].astype(int)
    length_band = reference_length_band(intent, df)
    out["length_unknown"] = out["length_mm"].isna() if length_band else False
    out.attrs["reference_length_band"] = length_band
    return out
