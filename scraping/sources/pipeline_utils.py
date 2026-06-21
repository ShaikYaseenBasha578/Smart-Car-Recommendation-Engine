"""Shared helpers for retained scraping maintenance scripts."""

from __future__ import annotations

import math
from typing import Any


APP_REQUIRED_FIELDS = (
    "make",
    "model",
    "variant",
    "price_ex_showroom",
    "fuel_type",
    "transmission",
    "body_type",
    "seating_capacity",
    "power_bhp",
    "torque_nm",
    "fuel_specific_efficiency",
    "airbags",
    "abs",
)


def canonical(wrapper: dict[str, Any]) -> dict[str, Any]:
    record = wrapper.get("canonical_record")
    return record if isinstance(record, dict) else wrapper


def version_id_for(wrapper: dict[str, Any]) -> str | None:
    value = wrapper.get("version_id") or canonical(wrapper).get("version_id")
    return str(value) if value not in (None, "") else None


def is_populated(value: Any) -> bool:
    return value not in (None, "", [], {})


def as_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def effective_efficiency_present(record: dict[str, Any]) -> bool:
    fuel = str(record.get("fuel_type") or "").strip().lower()
    if fuel == "cng":
        return is_populated(record.get("mileage_arai_km_per_kg"))
    if fuel == "electric":
        return is_populated(record.get("claimed_ev_range_km"))
    return is_populated(record.get("mileage_arai_kmpl"))


def range_issues(record: dict[str, Any]) -> list[str]:
    issues = []
    checks = (
        ("price_ex_showroom", 100000, 10000000),
        ("seating_capacity", 2, 9),
        ("airbags", 0, 12),
        ("mileage_arai_kmpl", 3, 45),
        ("mileage_arai_km_per_kg", 5, 45),
        ("power_bhp", 20, 800),
        ("torque_nm", 40, 1500),
        ("engine_cc", 600, 6000),
    )
    for field, low, high in checks:
        value = as_float(record.get(field))
        if value is None:
            continue
        if value < low or value > high:
            issues.append(field)
    fuel = str(record.get("fuel_type") or "").strip().lower()
    if fuel == "electric" and record.get("engine_cc") is not None:
        issues.append("engine_cc")
    if fuel == "electric" and (record.get("mileage_arai_kmpl") is not None or record.get("mileage_arai_km_per_kg") is not None):
        issues.append("mileage")
    if fuel == "cng" and record.get("mileage_arai_kmpl") is not None:
        issues.append("mileage_arai_kmpl")
    return sorted(set(issues))


def recommendation_status(record: dict[str, Any]) -> tuple[str, list[str]]:
    missing = []
    for field in APP_REQUIRED_FIELDS:
        if field == "fuel_specific_efficiency":
            if not effective_efficiency_present(record):
                missing.append(field)
        elif not is_populated(record.get(field)):
            missing.append(field)
    issues = range_issues(record)
    if not missing and not issues:
        return "recommendation_ready", []
    if any(field in missing for field in ("make", "model", "variant", "price_ex_showroom", "fuel_type", "transmission")):
        return "blocked", missing + issues
    return "partially_ready", missing + issues
