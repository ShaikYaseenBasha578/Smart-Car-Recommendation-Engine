"""Car detail for one model: GET /api/car/<make_slug>/<model_slug>?q=&drop=&variant_id=

Everything comes from the KB catalogue export. With a query (q, drop), each variant's
matches_query is "passes filter_v2 for that query", computed exactly as /predict does, and the
default selected variant is the one /predict shows on the model's card.

Spec items: {label, value_display, status}. status is "ok" (a value), "unverified" (blank, or
listed in the row's unverified_fields) or "not_applicable" (e.g. engine cc on an EV).
"""

from __future__ import annotations

import math

import pandas as pd

from services.catalogue import get_catalogue
from services.filter_v2 import filter_candidates
from services.images import find_car_image, image_attribution
from services.intent_v2 import parse_intent
from services.new_car_service import (
    TRANSMISSION_LABELS, apply_drops, data_as_of, format_cardekho_url, safe_slug, safety_summary,
)
from services.ranking_adapter import KMPL_UNTRUSTED_FUELS, rank_candidates
from services.summary import build_summary

# blanks that are expected for a fuel type (same rule as scripts/export_catalogue_from_kb.py)
NOT_APPLICABLE = {
    "electric": {"engine_cc", "mileage_kmpl", "mileage_km_per_kg", "fuel_tank_litres"},
    "petrol": {"ev_range_km", "mileage_km_per_kg"},
    "diesel": {"ev_range_km", "mileage_km_per_kg"},
    "hybrid": {"ev_range_km", "mileage_km_per_kg"},
    "cng": {"ev_range_km"},
}
FUEL_LABELS = {"petrol": "Petrol", "diesel": "Diesel", "cng": "CNG", "hybrid": "Petrol hybrid", "electric": "Electric"}

# (group, [(column, label, kind)]); kind: a unit suffix, "bool", "text" or a special key
SPEC_GROUPS = [
    ("Engine & performance", [
        ("engine_cc", "Engine", " cc"),
        ("power_bhp", "Power", " bhp"),
        ("torque_nm", "Torque", " Nm"),
        ("transmission_type", "Gearbox", "transmission"),
        ("drivetrain", "Drivetrain", "text"),
        ("fuel_type", "Fuel", "fuel"),
        ("mileage_kmpl", "Mileage (ARAI)", " kmpl"),
        ("mileage_km_per_kg", "CNG mileage (ARAI)", " km/kg"),
        ("ev_range_km", "Range (claimed)", " km"),
        ("fuel_tank_litres", "Fuel tank", " litres"),
    ]),
    ("Dimensions & capacity", [
        ("seats", "Seats", ""),
        ("length_mm", "Length", " mm"),
        ("width_mm", "Width", " mm"),
        ("height_mm", "Height", " mm"),
        ("wheelbase_mm", "Wheelbase", " mm"),
        ("ground_clearance_mm", "Ground clearance", " mm"),
        ("boot_space_litres", "Boot space", " litres"),
        ("kerb_weight_kg", "Kerb weight", " kg"),
    ]),
    ("Comfort & convenience", [
        ("auto_climate_control", "Automatic climate control", "bool"),
        ("rear_ac_vents", "Rear AC vents", "bool"),
        ("sunroof", "Sunroof", "bool"),
        ("ventilated_front_seats", "Ventilated front seats", "bool"),
        ("cruise_control", "Cruise control", "bool"),
        ("wireless_charging", "Wireless charging", "bool"),
        ("paddle_shifters", "Paddle shifters", "bool"),
    ]),
    ("Technology", [
        ("android_auto", "Android Auto", "bool"),
        ("apple_carplay", "Apple CarPlay", "bool"),
        ("connected_car_features", "Connected car tech", "bool"),
        ("heads_up_display", "Heads-up display", "bool"),
    ]),
    ("Safety", [
        ("airbags", "Airbags", ""),
        ("abs", "ABS", "bool"),
        ("esc", "Electronic stability control (ESC)", "bool"),
        ("hill_hold", "Hill hold assist", "bool"),
        ("tpms", "Tyre pressure monitoring (TPMS)", "bool"),
        ("rear_parking_sensors", "Rear parking sensors", "bool"),
        ("rear_camera", "Rear camera", "bool"),
        ("camera_360", "360° camera", "bool"),
        ("adas_available", "ADAS", "bool"),
    ]),
    # The KB has no warranty in its quarantine-aware read path, so nothing is exported for it.
    ("Warranty", [
        (None, "Standard warranty", "missing"),
    ]),
]
COLUMN_ALIASES = {"hill_hold": "hill_assist"}


def _blank(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _number(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:g}"


def _status(row, col: str) -> str:
    if col in NOT_APPLICABLE.get(row["fuel_type"], set()):
        return "not_applicable"
    return "unverified"


def spec_item(row, col: str | None, label: str, kind: str) -> dict:
    if kind == "missing":
        return {"label": label, "value_display": None, "status": "unverified"}
    col = COLUMN_ALIASES.get(col, col)
    value = row[col]
    if col == "mileage_kmpl" and row["fuel_type"] in KMPL_UNTRUSTED_FUELS:
        value = None  # the KB's kmpl cell on CNG rows holds the CNG figure; not shown as kmpl
    if _blank(value) or col in row["unverified_fields"]:
        return {"label": label, "value_display": None, "status": _status(row, col)}
    if kind == "bool":
        display = "Yes" if value is True else "No"
    elif kind == "transmission":
        display = TRANSMISSION_LABELS[value]
    elif kind == "fuel":
        display = FUEL_LABELS.get(value, value)
    elif kind == "text":
        display = str(value)
    else:
        display = _number(value) + kind
    return {"label": label, "value_display": display, "status": "ok"}


def mileage_display(row) -> dict:
    """What the card / variants table shows for efficiency, in the variant's own unit."""
    fuel = row["fuel_type"]
    if fuel == "electric":
        v = row["ev_range_km"]
        return {"label": "Range", "value": None if _blank(v) else f"{v:.0f} km", "unit": "km"}
    if fuel == "cng":
        v = row["mileage_km_per_kg"]
        return {"label": "Mileage", "value": None if _blank(v) else f"{v:g} km/kg (CNG)", "unit": "km/kg"}
    v = row["mileage_kmpl"]
    return {"label": "Mileage", "value": None if _blank(v) else f"{v:g} kmpl", "unit": "kmpl"}


def _unverified_labels(row) -> list[str]:
    labels = {col: label for _, items in SPEC_GROUPS for col, label, _ in items if col}
    labels["hill_assist"] = labels.pop("hill_hold")
    return [labels[c] for c in sorted(row["unverified_fields"]) if c in labels]


def find_model(make_slug: str, model_slug: str) -> pd.DataFrame | None:
    df = get_catalogue()
    rows = df[(df["make"].map(safe_slug) == make_slug.lower()) & (df["model"].map(safe_slug) == model_slug.lower())]
    return None if rows.empty else rows


def _query_matches(q: str, drop: list[str], model: str) -> tuple[set[int], int | None]:
    """(variant_ids of this model passing the query's filters, the variant /predict would show)."""
    intent, _ = apply_drops(parse_intent(q), drop)
    candidates = filter_candidates(intent, get_catalogue())
    mine = candidates[candidates["model"] == model]
    if mine.empty:
        return set(), None
    ranked, _ = rank_candidates(intent, candidates)
    best = ranked.loc[ranked["model"] == model, "variant_id"]
    return set(mine["variant_id"].astype(int)), int(best.iloc[0])


def get_car_detail(make_slug: str, model_slug: str, q: str = "", drop: list[str] | None = None,
                   variant_id: int | None = None, app_root_path: str = ".") -> dict | None:
    rows = find_model(make_slug, model_slug)
    if rows is None:
        return None
    rows = rows.sort_values(["price_ex_showroom", "variant_id"])
    first = rows.iloc[0]

    matching, best = _query_matches(q, drop or [], first["model"]) if q.strip() else (set(), None)
    ids = set(rows["variant_id"].astype(int))
    if variant_id in ids:
        selected = variant_id
    elif best is not None:
        selected = best
    else:
        selected = int(first["variant_id"])
    row = rows.loc[selected]

    variants = []
    for _, r in rows.iterrows():
        vid = int(r["variant_id"])
        variants.append({
            "variant_id": vid,
            "variant": r["variant"],
            "price": None if _blank(r["price_ex_showroom"]) else float(r["price_ex_showroom"]),
            "transmission_type": r["transmission_type"],
            "transmission_label": TRANSMISSION_LABELS[r["transmission_type"]],
            "fuel_type": r["fuel_type"],
            "fuel_label": FUEL_LABELS.get(r["fuel_type"], r["fuel_type"]),
            "mileage_kmpl": None if _blank(r["mileage_kmpl"]) or r["fuel_type"] in KMPL_UNTRUSTED_FUELS
            else float(r["mileage_kmpl"]),
            "mileage_km_per_kg": None if _blank(r["mileage_km_per_kg"]) else float(r["mileage_km_per_kg"]),
            "ev_range_km": None if _blank(r["ev_range_km"]) else int(r["ev_range_km"]),
            "mileage_display": mileage_display(r),
            "matches_query": vid in matching,
            "unverified": _unverified_labels(r),
        })

    prices = rows["price_ex_showroom"].dropna()
    return {
        "make": first["make"],
        "model": first["model"],
        "make_slug": safe_slug(first["make"]),
        "model_slug": safe_slug(first["model"]),
        "body_type": first["body_type"],
        "image": find_car_image(app_root_path, first["make"], first["model"], first["body_type"]),
        "image_attribution": image_attribution(app_root_path, first["make"], first["model"]),
        "cardekho_link": format_cardekho_url(first["make"], first["model"]),
        "price_range": {"min": float(prices.min()), "max": float(prices.max())} if not prices.empty else None,
        "data_as_of": data_as_of(),
        "summary": build_summary(rows, TRANSMISSION_LABELS),
        "query": {"q": q, "drop": drop or [], "matching_variant_count": len(matching)} if q.strip() else None,
        "variants": variants,
        "selected_variant_id": selected,
        "specs": [
            {"group": group, "items": [spec_item(row, col, label, kind) for col, label, kind in items]}
            for group, items in SPEC_GROUPS
        ],
        "safety": safety_summary(row),
    }
