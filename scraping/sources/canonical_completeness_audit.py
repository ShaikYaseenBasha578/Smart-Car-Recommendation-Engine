"""Audit canonical field and record completeness for the processed pilot dataset."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from scraping.enrichment.missing_field_detector import prioritized_enrichment_queue
from scraping.enrichment.validators import suspicious_repeated_value, validate_candidate
from scraping.schemas.new_car_schema import BOOLEAN_COLUMNS, NEW_CAR_COLUMNS, NUMERIC_COLUMNS
from scraping.schemas.null_reasons import field_null_reason


ROOT = Path(__file__).resolve().parents[2]
READY_DATASET = ROOT / "datasets/processed/carrec_canonical_recommendation_ready.json"
POLICY_PATH = ROOT / "scraping/config/field_enrichment_policy.json"
OUTPUT_DIR = ROOT / "scraping/outputs"

FIELD_JSON = OUTPUT_DIR / "canonical_field_completeness.json"
FIELD_CSV = OUTPUT_DIR / "canonical_field_completeness.csv"
FIELD_MD = OUTPUT_DIR / "canonical_field_completeness.md"
RECORD_JSON = OUTPUT_DIR / "canonical_record_completeness.json"
RECORD_CSV = OUTPUT_DIR / "canonical_record_completeness.csv"
QUEUE_JSON = OUTPUT_DIR / "enrichment_queue.json"
QUEUE_CSV = OUTPUT_DIR / "enrichment_queue.csv"
QUEUE_MD = OUTPUT_DIR / "enrichment_queue_summary.md"
PILOT_PLAN_JSON = OUTPUT_DIR / "pilot_enrichment_plan.json"
PILOT_PLAN_MD = OUTPUT_DIR / "pilot_enrichment_plan.md"


PROVENANCE_BLOCKS = (
    "field_provenance",
    "enrichment_provenance",
    "coverage_enrichment_provenance",
    "cardekho_critical_provenance",
    "final_dataset_resolution_provenance",
    "conflict_metadata",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(wrapper: dict[str, Any]) -> dict[str, Any]:
    return wrapper.get("canonical_record") if isinstance(wrapper.get("canonical_record"), dict) else wrapper


def populated(value: Any) -> bool:
    return value not in (None, "", [], {})


def record_identity(wrapper: dict[str, Any]) -> str:
    record = canonical(wrapper)
    return str(
        wrapper.get("version_id")
        or "|".join(str(record.get(field) or "") for field in ("make", "model", "variant", "fuel_type", "transmission"))
    )


def provenance_for_field(wrapper: dict[str, Any], field: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for block_name in PROVENANCE_BLOCKS:
        block = wrapper.get(block_name)
        if not isinstance(block, dict):
            continue
        if field in block:
            value = block[field]
            if isinstance(value, list):
                matches.extend(item for item in value if isinstance(item, dict))
            elif isinstance(value, dict):
                value = dict(value)
                value.setdefault("provenance_block", block_name)
                matches.append(value)
        for item in block.values():
            if isinstance(item, dict) and item.get("field") == field:
                item = dict(item)
                item.setdefault("provenance_block", block_name)
                matches.append(item)
    return matches


def group_key(record: dict[str, Any], group: str) -> str:
    value = record.get(group)
    return str(value) if populated(value) else "UNKNOWN"


def field_availability(records: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total = len(records)
    for field in NEW_CAR_COLUMNS:
        values = [canonical(wrapper).get(field) for wrapper in records]
        field_policy = policy[field]
        populated_count = sum(1 for value in values if populated(value))
        not_applicable_count = sum(
            1 for wrapper in records if field_null_reason(field, canonical(wrapper), policy) == "NOT_APPLICABLE"
        )
        applicable_total = total - not_applicable_count
        missing_applicable = max(applicable_total - populated_count, 0)
        provenance_count = sum(1 for wrapper in records if provenance_for_field(wrapper, field))
        invalid_count = 0
        suspicious_count = 0
        examples = []
        for wrapper in records:
            record = canonical(wrapper)
            value = record.get(field)
            if populated(value):
                issues = validate_candidate(record, field, value)
                if issues:
                    invalid_count += 1
                if len(examples) < 5:
                    examples.append(value)
        if suspicious_repeated_value(field, values):
            suspicious_count += 1

        coverage_by = {}
        for group in ("model", "fuel_type", "transmission", "body_type"):
            buckets = defaultdict(lambda: {"records": 0, "populated": 0})
            for wrapper in records:
                record = canonical(wrapper)
                key = group_key(record, group)
                buckets[key]["records"] += 1
                if populated(record.get(field)):
                    buckets[key]["populated"] += 1
            coverage_by[group] = {
                key: {
                    **counts,
                    "populated_pct": round(counts["populated"] / counts["records"] * 100, 2) if counts["records"] else 0.0,
                }
                for key, counts in sorted(buckets.items())
            }

        rows.append(
            {
                "field": field,
                "category": field_policy["category"],
                "expected_scope": field_policy["expected_scope"],
                "recommendation_importance": field_policy["recommendation_importance"],
                "applicable_records": applicable_total,
                "populated_count": populated_count,
                "missing_applicable_count": missing_applicable,
                "not_applicable_count": not_applicable_count,
                "populated_pct": round(populated_count / applicable_total * 100, 2) if applicable_total else 100.0,
                "provenance_count": provenance_count,
                "unique_populated_values": len({json.dumps(value, sort_keys=True, default=str) for value in values if populated(value)}),
                "invalid_value_count": invalid_count,
                "suspicious_pattern_count": suspicious_count,
                "mostly_repeated": suspicious_repeated_value(field, values),
                "value_examples": examples,
                "preferred_source": field_policy["preferred_source"],
                "allows_inheritance": field_policy["inheritance"]["allowed"],
                "coverage_by_model": coverage_by["model"],
                "coverage_by_fuel_type": coverage_by["fuel_type"],
                "coverage_by_transmission": coverage_by["transmission"],
                "coverage_by_body_type": coverage_by["body_type"],
            }
        )
    return rows


def record_availability(records: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for wrapper in records:
        record = canonical(wrapper)
        missing = []
        applicable = 0
        populated_count = 0
        weighted_total = 0
        weighted_populated = 0
        missing_by_category = Counter()
        invalid_fields = []
        for field in NEW_CAR_COLUMNS:
            if field_null_reason(field, record, policy) == "NOT_APPLICABLE":
                continue
            applicable += 1
            weight = policy[field]["recommendation_importance"]
            weighted_total += weight
            value = record.get(field)
            if populated(value):
                populated_count += 1
                weighted_populated += weight
                issues = validate_candidate(record, field, value)
                if issues:
                    invalid_fields.append({"field": field, "issues": issues})
            else:
                missing.append(field)
                missing_by_category[policy[field]["category"]] += 1
        rows.append(
            {
                "record_id": record_identity(wrapper),
                "make": record.get("make"),
                "model": record.get("model"),
                "variant": record.get("variant"),
                "fuel_type": record.get("fuel_type"),
                "transmission": record.get("transmission"),
                "body_type": record.get("body_type"),
                "applicable_field_count": applicable,
                "populated_field_count": populated_count,
                "missing_field_count": len(missing),
                "plain_completeness_pct": round(populated_count / applicable * 100, 2) if applicable else 100.0,
                "weighted_completeness_pct": round(weighted_populated / weighted_total * 100, 2) if weighted_total else 100.0,
                "missing_fields": missing,
                "missing_by_category": dict(missing_by_category),
                "invalid_fields": invalid_fields,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_queue_outputs(records: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    queue = prioritized_enrichment_queue(records, policy)
    QUEUE_JSON.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(
        QUEUE_CSV,
        queue,
        [
            "record_id",
            "make",
            "model",
            "variant",
            "fuel_type",
            "transmission",
            "missing_field",
            "field_priority",
            "category",
            "field_scope",
            "preferred_source",
            "fallback_source",
            "inheritance_possibility",
            "estimated_difficulty",
            "manual_review_likelihood",
        ],
    )

    by_field = Counter(item["missing_field"] for item in queue)
    by_category = Counter(item["category"] for item in queue)
    lines = [
        "# Enrichment Queue Summary",
        "",
        f"- Queue entries: {len(queue)}",
        f"- Affected fields: {len(by_field)}",
        "",
        "## Top Missing Fields",
        "",
        "| Field | Missing applicable records |",
        "|---|---:|",
    ]
    for field, count in by_field.most_common(20):
        lines.append(f"| `{field}` | {count} |")
    lines.extend(["", "## Queue By Category", "", "| Category | Entries |", "|---|---:|"])
    for category, count in by_category.most_common():
        lines.append(f"| {category} | {count} |")
    QUEUE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return queue


def write_pilot_plan(queue: list[dict[str, Any]]) -> dict[str, Any]:
    by_source = defaultdict(list)
    for item in queue:
        if item["category"] in {"CORE_REQUIRED", "HIGH_VALUE", "SPECIALIST"}:
            by_source[item["preferred_source"]].append(item)
    plan = {
        "purpose": "Small controlled enrichment pilots before any broad scraping or merging.",
        "pilot_order": [
            {
                "stage": 1,
                "name": "OEM brochure/spec-sheet adapter pilot",
                "target_fields": ["mileage_arai_kmpl", "mileage_arai_km_per_kg", "claimed_ev_range_km", "battery_capacity_kwh"],
                "sample_size": "10-15 records across Petrol, Diesel, CNG, and EV",
                "acceptance_gate": "high-confidence exact model/powertrain evidence with unit-safe mileage separation",
            },
            {
                "stage": 2,
                "name": "Exact-variant feature enrichment pilot",
                "target_fields": ["ebd", "esc", "rear_camera", "camera_360", "automatic_climate_control"],
                "sample_size": "base and high trims for each pilot model",
                "acceptance_gate": "explicit Yes/No/Available labels; missing remains null",
            },
            {
                "stage": 3,
                "name": "Model-shared dimension enrichment pilot",
                "target_fields": ["length_mm", "width_mm", "height_mm", "wheelbase_mm", "boot_space_litres"],
                "sample_size": "one verified model page plus conflicting powertrain checks per model",
                "acceptance_gate": "explicit model-level or powertrain-level evidence; conflicts withheld",
            },
        ],
        "top_priority_sources": {source: len(items) for source, items in sorted(by_source.items())},
        "do_not_fill_yet": [
            "subjective ownership scores",
            "ADAS detail booleans without exact variant evidence",
            "real-world mileage",
            "ambiguous special-edition feature differences",
        ],
    }
    PILOT_PLAN_JSON.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Pilot Enrichment Plan",
        "",
        "This plan intentionally stages enrichment work before broad crawling or merging.",
        "",
    ]
    for stage in plan["pilot_order"]:
        lines.extend(
            [
                f"## {stage['stage']}. {stage['name']}",
                "",
                f"- Target fields: {', '.join(stage['target_fields'])}",
                f"- Sample size: {stage['sample_size']}",
                f"- Acceptance gate: {stage['acceptance_gate']}",
                "",
            ]
        )
    lines.extend(["## Deferred", ""])
    lines.extend(f"- {item}" for item in plan["do_not_fill_yet"])
    PILOT_PLAN_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan


def write_markdown(field_rows: list[dict[str, Any]], record_rows: list[dict[str, Any]]) -> None:
    by_category = defaultdict(list)
    for row in field_rows:
        by_category[row["category"]].append(row)
    poorest = sorted(field_rows, key=lambda row: (row["populated_pct"], -row["recommendation_importance"]))[:15]
    best = sorted(field_rows, key=lambda row: (-row["populated_pct"], -row["recommendation_importance"]))[:15]
    lines = [
        "# Canonical Field Completeness Audit",
        "",
        f"- Records audited: {len(record_rows)}",
        f"- Average plain record completeness: {round(mean(row['plain_completeness_pct'] for row in record_rows), 2)}%",
        f"- Average weighted record completeness: {round(mean(row['weighted_completeness_pct'] for row in record_rows), 2)}%",
        "",
        "## Coverage By Category",
        "",
        "| Category | Fields | Average coverage |",
        "|---|---:|---:|",
    ]
    for category, rows in sorted(by_category.items()):
        lines.append(f"| {category} | {len(rows)} | {round(mean(row['populated_pct'] for row in rows), 2)}% |")
    lines.extend(["", "## Poorest Covered Fields", "", "| Field | Category | Scope | Coverage | Preferred source |", "|---|---|---|---:|---|"])
    for row in poorest:
        lines.append(
            f"| `{row['field']}` | {row['category']} | {row['expected_scope']} | {row['populated_pct']}% | {row['preferred_source']} |"
        )
    lines.extend(["", "## Best Covered Fields", "", "| Field | Category | Scope | Coverage |", "|---|---|---|---:|"])
    for row in best:
        lines.append(f"| `{row['field']}` | {row['category']} | {row['expected_scope']} | {row['populated_pct']}% |")
    FIELD_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = load_json(READY_DATASET)
    policy = load_json(POLICY_PATH)

    field_rows = field_availability(records, policy)
    record_rows = record_availability(records, policy)
    FIELD_JSON.write_text(json.dumps(field_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    RECORD_JSON.write_text(json.dumps(record_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(
        FIELD_CSV,
        field_rows,
        [
            "field",
            "category",
            "expected_scope",
            "recommendation_importance",
            "applicable_records",
            "populated_count",
            "missing_applicable_count",
            "not_applicable_count",
            "populated_pct",
            "provenance_count",
            "unique_populated_values",
            "invalid_value_count",
            "suspicious_pattern_count",
            "mostly_repeated",
            "preferred_source",
            "allows_inheritance",
        ],
    )
    write_csv(
        RECORD_CSV,
        record_rows,
        [
            "record_id",
            "make",
            "model",
            "variant",
            "fuel_type",
            "transmission",
            "body_type",
            "applicable_field_count",
            "populated_field_count",
            "missing_field_count",
            "plain_completeness_pct",
            "weighted_completeness_pct",
        ],
    )
    queue = write_queue_outputs(records, policy)
    write_pilot_plan(queue)
    write_markdown(field_rows, record_rows)

    print(
        json.dumps(
            {
                "records": len(records),
                "fields": len(field_rows),
                "avg_plain_completeness": round(mean(row["plain_completeness_pct"] for row in record_rows), 2),
                "avg_weighted_completeness": round(mean(row["weighted_completeness_pct"] for row in record_rows), 2),
                "queue_entries": len(queue),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
