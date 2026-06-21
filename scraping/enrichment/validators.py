"""Reusable validation hooks for enrichment candidates."""

from __future__ import annotations

from typing import Any


NUMERIC_RANGES = {
    "price_ex_showroom": (100000, 10000000),
    "engine_cc": (600, 6000),
    "power_bhp": (20, 800),
    "torque_nm": (40, 1500),
    "airbags": (0, 12),
    "mileage_arai_kmpl": (3, 45),
    "mileage_arai_km_per_kg": (5, 45),
    "claimed_ev_range_km": (50, 1000),
    "battery_capacity_kwh": (5, 250),
    "seating_capacity": (2, 9),
    "boot_space_litres": (0, 1000),
    "ground_clearance_mm": (100, 300),
    "fuel_tank_capacity_litres": (15, 120),
    "length_mm": (2500, 6000),
    "width_mm": (1200, 2500),
    "height_mm": (1000, 2500),
    "wheelbase_mm": (1500, 3500),
    "kerb_weight_kg": (500, 3500),
    "turning_radius_metres": (3, 8),
}


def normalize_fuel(value: Any) -> str:
    return str(value or "").strip().lower()


def validate_numeric_range(field_name: str, value: Any) -> list[str]:
    if value in (None, "") or field_name not in NUMERIC_RANGES:
        return []
    low, high = NUMERIC_RANGES[field_name]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return [f"{field_name} is not numeric"]
    if number < low or number > high:
        return [f"{field_name}={value} outside range {low}-{high}"]
    return []


def validate_fuel_applicability(record: dict, field_name: str, value: Any) -> list[str]:
    fuel = normalize_fuel(record.get("fuel_type"))
    if value in (None, ""):
        return []
    if fuel == "electric" and field_name in {"engine_cc", "fuel_tank_capacity_litres", "mileage_arai_kmpl", "mileage_arai_km_per_kg"}:
        return [f"{field_name} should be null for EV"]
    if fuel == "electric" and field_name in {"cylinders", "turbocharged"}:
        return [f"{field_name} should be null for EV"]
    if fuel != "electric" and field_name in {"battery_capacity_kwh", "claimed_ev_range_km", "charging_time_ac_hours", "charging_time_dc_minutes"}:
        return [f"{field_name} applies only to EV records"]
    if fuel == "cng" and field_name == "mileage_arai_kmpl":
        return ["CNG mileage must not be stored as km/l"]
    if fuel != "cng" and field_name == "mileage_arai_km_per_kg":
        return ["km/kg mileage applies only to CNG"]
    return []


def validate_candidate(record: dict, field_name: str, value: Any) -> list[str]:
    return validate_numeric_range(field_name, value) + validate_fuel_applicability(record, field_name, value)


def suspicious_repeated_value(field_name: str, values: list[Any], threshold: float = 0.95) -> bool:
    populated = [value for value in values if value not in (None, "", [], {})]
    if len(populated) < 10:
        return False
    most_common = max(populated.count(value) for value in set(populated))
    return most_common / len(populated) >= threshold and field_name not in {"body_type", "source", "currency"}
