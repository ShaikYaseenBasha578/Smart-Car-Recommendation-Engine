"""Standard null-reason metadata for canonical enrichment."""

from __future__ import annotations

NULL_REASONS = (
    "NOT_APPLICABLE",
    "NOT_YET_ENRICHED",
    "SOURCE_UNAVAILABLE",
    "FIELD_NOT_PUBLISHED",
    "UNRESOLVED_CONFLICT",
    "LOW_CONFIDENCE_MATCH",
    "UNSAFE_TO_INHERIT",
    "EXTRACTION_FAILED",
    "SUBJECTIVE_REQUIRES_DERIVATION",
    "DEFERRED_FIELD",
)


def null_metadata(field_name: str, null_reason: str = "NOT_YET_ENRICHED", notes: str | None = None) -> dict:
    """Return backward-compatible metadata for a null flat-record field."""
    if null_reason not in NULL_REASONS:
        raise ValueError(f"Unsupported null reason: {null_reason}")
    return {
        field_name: {
            "value": None,
            "null_reason": null_reason,
            "notes": notes,
        }
    }


def field_null_reason(field_name: str, record: dict, policy: dict | None = None) -> str | None:
    """Infer a conservative null reason without mutating the canonical record."""
    if record.get(field_name) is not None:
        return None
    fuel = str(record.get("fuel_type") or "").lower()
    if policy:
        fuel_types = policy.get(field_name, {}).get("applicable_fuel_types") or ["ALL"]
        normalized_fuel_types = {str(value).lower() for value in fuel_types}
        if "all" not in normalized_fuel_types and fuel and fuel not in normalized_fuel_types:
            return "NOT_APPLICABLE"
    if field_name in {"reliability_score", "resale_value_score", "service_network_score"}:
        return "SUBJECTIVE_REQUIRES_DERIVATION"
    if fuel == "electric" and field_name in {"engine_cc", "cylinders", "fuel_tank_capacity_litres", "mileage_arai_kmpl", "mileage_arai_km_per_kg"}:
        return "NOT_APPLICABLE"
    if fuel != "electric" and field_name in {"battery_capacity_kwh", "claimed_ev_range_km", "charging_time_ac_hours", "charging_time_dc_minutes"}:
        return "NOT_APPLICABLE"
    return "NOT_YET_ENRICHED"
