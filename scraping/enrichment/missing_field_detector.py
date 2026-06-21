"""Detect missing applicable fields and produce a prioritized queue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scraping.schemas.new_car_schema import NEW_CAR_COLUMNS
from scraping.schemas.null_reasons import field_null_reason


def canonical(wrapper: dict[str, Any]) -> dict[str, Any]:
    return wrapper.get("canonical_record") if isinstance(wrapper.get("canonical_record"), dict) else wrapper


def load_canonical_records(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_policy(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def field_applicable(record: dict, field_name: str, policy: dict) -> bool:
    reason = field_null_reason(field_name, record, policy)
    return reason != "NOT_APPLICABLE"


def missing_fields_for_record(wrapper: dict, policy: dict) -> list[dict]:
    record = canonical(wrapper)
    record_id = str(wrapper.get("version_id") or "|".join(str(record.get(k)) for k in ("make", "model", "variant", "fuel_type", "transmission")))
    missing = []
    for field in NEW_CAR_COLUMNS:
        if not field_applicable(record, field, policy):
            continue
        if record.get(field) not in (None, "", [], {}):
            continue
        field_policy = policy[field]
        missing.append(
            {
                "record_id": record_id,
                "make": record.get("make"),
                "model": record.get("model"),
                "variant": record.get("variant"),
                "fuel_type": record.get("fuel_type"),
                "transmission": record.get("transmission"),
                "missing_field": field,
                "field_priority": field_policy["recommendation_importance"],
                "category": field_policy["category"],
                "field_scope": field_policy["expected_scope"],
                "applicability": {
                    "vehicle_types": field_policy["applicable_vehicle_types"],
                    "fuel_types": field_policy["applicable_fuel_types"],
                },
                "preferred_source": field_policy["preferred_source"],
                "fallback_source": field_policy["fallback_sources"][0] if field_policy.get("fallback_sources") else None,
                "inheritance_possibility": field_policy["inheritance"]["allowed"],
                "estimated_difficulty": field_policy.get("estimated_difficulty", "medium"),
                "manual_review_likelihood": field_policy.get("manual_review_likelihood", "medium"),
            }
        )
    return missing


def prioritized_enrichment_queue(
    records: list[dict],
    policy: dict,
    model: str | None = None,
    field: str | None = None,
    category: str | None = None,
    source_class: str | None = None,
) -> list[dict]:
    entries = []
    field_counts: dict[str, int] = {}
    for wrapper in records:
        for item in missing_fields_for_record(wrapper, policy):
            if model and item["model"] != model:
                continue
            if field and item["missing_field"] != field:
                continue
            if category and item["category"] != category:
                continue
            if source_class and source_class not in [item["preferred_source"], item["fallback_source"]]:
                continue
            entries.append(item)
            field_counts[item["missing_field"]] = field_counts.get(item["missing_field"], 0) + 1
    difficulty_rank = {"low": 0, "medium": 1, "high": 2}
    entries.sort(
        key=lambda item: (
            -item["field_priority"],
            -field_counts.get(item["missing_field"], 0),
            0 if item["preferred_source"].startswith("Official") else 1,
            0 if item["inheritance_possibility"] else 1,
            difficulty_rank.get(item["estimated_difficulty"], 1),
            item["model"] or "",
            item["variant"] or "",
        )
    )
    return entries

