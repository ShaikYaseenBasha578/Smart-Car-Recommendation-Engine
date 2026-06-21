"""Build final audited canonical recommendation datasets.

The builder applies only high-confidence review decisions to an in-memory copy
of the interim records, then writes processed JSON/CSV subsets. It does not
modify Flask, ranking logic, or the existing production dataset.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scraping.schemas.new_car_schema import (
    BOOLEAN_COLUMNS,
    NEW_CAR_COLUMNS,
    NUMERIC_COLUMNS,
    REQUIRED_COLUMNS,
    calculate_field_completeness,
    validate_schema_columns,
)
from scraping.sources.pipeline_utils import canonical, recommendation_status, version_id_for


INPUT_ROOT = Path("datasets/interim/cosmetic_variant_recovered")
PROCESSED_ROOT = Path("datasets/processed")
REVIEW_PATH = Path("scraping/outputs/remaining_record_review.json")
QUARANTINE_PATH = Path("scraping/outputs/quarantined_records.json")
MANUAL_REVIEW_PATH = Path("scraping/outputs/manual_review_required.json")
MILEAGE_CONFLICT_PATH = Path("scraping/outputs/mileage_conflict_review.json")
ENGINE_REPAIR_REPORT_PATH = Path("scraping/outputs/engine_cc_repair_report.json")

READY_JSON_PATH = PROCESSED_ROOT / "carrec_canonical_recommendation_ready.json"
NULLABLE_JSON_PATH = PROCESSED_ROOT / "carrec_canonical_nullable_usable.json"
EXCLUDED_JSON_PATH = PROCESSED_ROOT / "carrec_canonical_excluded.json"
READY_CSV_PATH = PROCESSED_ROOT / "carrec_canonical_recommendation_ready.csv"
NULLABLE_CSV_PATH = PROCESSED_ROOT / "carrec_canonical_nullable_usable.csv"

REPORT_JSON_PATH = Path("scraping/outputs/final_dataset_build_report.json")
REPORT_MD_PATH = Path("scraping/outputs/final_dataset_build_report.md")
APPLIED_RESOLUTIONS_PATH = Path("scraping/outputs/final_dataset_applied_resolutions.json")

TARGET_FIELDS = (
    "mileage_arai_kmpl",
    "mileage_arai_km_per_kg",
    "airbags",
    "abs",
    "cruise_control",
    "android_auto",
    "apple_carplay",
)
RECOMMENDATION_CRITICAL_FIELDS = (
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
PROTECTED_FIELDS = ("make", "model", "variant", "full_name", "price_ex_showroom", "fuel_type", "transmission", "power_bhp", "torque_nm")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_models() -> list[dict[str, Any]]:
    items = []
    for path in sorted(INPUT_ROOT.glob("*/enriched_records.json")):
        for wrapper in read_json(path, []):
            items.append({"model_slug": path.parent.name, "wrapper": wrapper, "record": canonical(wrapper), "version_id": version_id_for(wrapper)})
    return items


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


def is_populated(value: Any) -> bool:
    return value not in (None, "", [], {})


def identity_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (record.get("make"), record.get("model"), record.get("variant"), record.get("fuel_type"), record.get("transmission"))


def identity_matches(record: dict[str, Any], expected: dict[str, Any]) -> bool:
    for field in ("make", "model", "variant", "fuel_type", "transmission", "price_ex_showroom"):
        if expected.get(field) != record.get(field):
            return False
    return True


def build_evidence_map(review: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = {}
    for item in read_json(Path("scraping/outputs/cosmetic_variant_recovery_rejected.json"), []):
        validation = item.get("validation_details") or {}
        parsed = (validation.get("parsed") or {})
        fields = parsed.get("parsed_fields") or {}
        field_evidence = parsed.get("field_evidence") or {}
        evidence[str(item.get("version_id"))] = {
            "url": item.get("url"),
            "parsed_fields": fields,
            "field_evidence": field_evidence,
            "validation_details": validation,
        }
    return evidence


def field_evidence(parsed_evidence: dict[str, Any], field: str) -> dict[str, Any] | None:
    if field in {"mileage_arai_kmpl", "mileage_arai_km_per_kg"}:
        mileage = parsed_evidence.get("mileage") or []
        return mileage[0] if mileage else None
    value = parsed_evidence.get(field)
    return value if isinstance(value, dict) else None


def values_agree(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    try:
        return round(float(left), 2) == round(float(right), 2)
    except (TypeError, ValueError):
        return left == right


def build_resolution_provenance(
    record: dict[str, Any],
    field: str,
    old_value: Any,
    new_value: Any,
    source_url: str | None,
    evidence: dict[str, Any] | None,
    decision: dict[str, Any],
    applied_at: str,
) -> dict[str, Any]:
    return {
        "field": field,
        "canonical_identity": {key: record.get(key) for key in ("make", "model", "variant", "fuel_type", "transmission")},
        "old_value": old_value,
        "new_value": new_value,
        "source_url": source_url,
        "raw_label": evidence.get("label") if evidence else None,
        "raw_value": evidence.get("raw_value") if evidence else None,
        "source_path": evidence.get("path") if evidence else None,
        "review_decision": decision.get("decision"),
        "evidence": decision.get("decision_evidence") or decision.get("evidence"),
        "confidence": decision.get("confidence"),
        "applied_at": applied_at,
    }


def apply_accept_after_review(records: list[dict[str, Any]], review: dict[str, Any], applied_at: str) -> list[dict[str, Any]]:
    by_version = {item["version_id"]: item for item in records}
    evidence_map = build_evidence_map(review)
    applied = []
    for decision in review.get("record_decisions") or []:
        if decision.get("decision") != "accept_after_review" or decision.get("confidence") != "high":
            continue
        version_id = str(decision.get("version_id"))
        item = by_version.get(version_id)
        if not item:
            continue
        record = item["record"]
        if not identity_matches(record, decision.get("canonical_identity") or {}):
            continue
        evidence = evidence_map.get(version_id) or {}
        parsed_fields = evidence.get("parsed_fields") or {}
        evidence_by_field = evidence.get("field_evidence") or {}
        wrapper = item["wrapper"]
        wrapper.setdefault("final_dataset_resolution_provenance", {})
        wrapper.setdefault("cardekho_critical_provenance", {})
        for field in decision.get("fields_safe_to_merge") or []:
            if field not in TARGET_FIELDS:
                continue
            new_value = parsed_fields.get(field)
            if new_value is None:
                continue
            old_value = record.get(field)
            if old_value is not None and not values_agree(old_value, new_value):
                continue
            if old_value is None:
                record[field] = new_value
            provenance = build_resolution_provenance(
                record,
                field,
                old_value,
                new_value,
                evidence.get("url"),
                field_evidence(evidence_by_field, field),
                decision,
                applied_at,
            )
            wrapper["final_dataset_resolution_provenance"][field] = provenance
            wrapper["cardekho_critical_provenance"][field] = provenance
            applied.append({"version_id": version_id, **provenance, "status": "applied" if old_value is None else "agreement"})
        record["field_completeness_score"] = calculate_field_completeness(record)
    return applied


def apply_engine_resolutions(records: list[dict[str, Any]], review: dict[str, Any], applied_at: str) -> list[dict[str, Any]]:
    by_version = {item["version_id"]: item for item in records}
    applied = []
    for decision in review.get("engine_cc_decisions") or []:
        if decision.get("decision") != "safely resolved":
            continue
        version_id = str(decision.get("version_id"))
        item = by_version.get(version_id)
        if not item:
            continue
        record = item["record"]
        expected = decision.get("identity") or {}
        if not identity_matches(record, expected):
            continue
        old_value = record.get("engine_cc")
        new_value = decision.get("resolved_value")
        record["engine_cc"] = new_value
        evidence = decision.get("evidence") or {}
        provenance = build_resolution_provenance(record, "engine_cc", old_value, new_value, evidence.get("source_url"), evidence, decision, applied_at)
        wrapper = item["wrapper"]
        wrapper.setdefault("final_dataset_resolution_provenance", {})["engine_cc"] = provenance
        wrapper.setdefault("field_provenance", {})["engine_cc"] = {
            "field": "engine_cc",
            "value": new_value,
            "level": "version_specific",
            "source_url": evidence.get("source_url"),
            "evidence": f"{evidence.get('label')}={evidence.get('raw_value')!r}",
            "confidence": decision.get("confidence") or "high",
        }
        applied.append({"version_id": version_id, **provenance, "status": "applied"})
        record["field_completeness_score"] = calculate_field_completeness(record)
    return applied


def apply_conflict_metadata(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_version = {item["version_id"]: item for item in records}
    conflicts = []
    for conflict in read_json(MILEAGE_CONFLICT_PATH, []):
        version_id = str(conflict.get("version_id"))
        item = by_version.get(version_id)
        if not item:
            continue
        record = item["record"]
        metadata = {
            "has_unresolved_conflict": True,
            "field": conflict.get("field"),
            "conflict_status": "unresolved",
            "canonical_value_kept": record.get(conflict.get("field")),
            "carwale_value": conflict.get("carwale_value"),
            "cardekho_value": conflict.get("cardekho_value"),
            "carwale_source_url": record.get("source_url"),
            "cardekho_source_url": ((conflict.get("source_page_identity") or {}).get("cardekho_url")),
            "rationale": conflict.get("rationale"),
        }
        item["wrapper"].setdefault("conflict_metadata", []).append(metadata)
        conflicts.append({"version_id": version_id, **metadata})
    return conflicts


def subset_records(records: list[dict[str, Any]], review: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    decision_by_id = {str(item.get("version_id")): item for item in review.get("record_decisions") or []}
    ready = []
    nullable = []
    excluded = []
    for item in records:
        version_id = item["version_id"]
        decision = decision_by_id.get(str(version_id))
        status, blockers = recommendation_status(item["record"])
        wrapper = item["wrapper"]
        wrapper.setdefault("final_dataset_status", {})
        if decision and decision.get("decision") == "accept_with_nullable_fields":
            wrapper["final_dataset_status"] = {"subset": "nullable_usable", "decision": decision}
            nullable.append(wrapper)
        elif decision and decision.get("decision") in {"quarantine", "reject"}:
            wrapper["final_dataset_status"] = {"subset": "excluded", "decision": decision}
            excluded.append(wrapper)
        elif status == "recommendation_ready":
            wrapper["final_dataset_status"] = {"subset": "recommendation_ready", "readiness_status": status}
            ready.append(wrapper)
        else:
            wrapper["final_dataset_status"] = {"subset": "excluded", "readiness_status": status, "blocking_fields": blockers}
            excluded.append(wrapper)
    return ready, nullable, excluded


def canonical_rows(wrappers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for wrapper in wrappers:
        record = canonical(wrapper)
        rows.append({field: record.get(field) for field in NEW_CAR_COLUMNS})
    return rows


def write_csv(path: Path, wrappers: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(NEW_CAR_COLUMNS))
        writer.writeheader()
        writer.writerows(canonical_rows(wrappers))


def effective_field(record: dict[str, Any], field: str) -> Any:
    if field == "fuel_specific_efficiency":
        fuel = str(record.get("fuel_type") or "").lower()
        if fuel == "cng":
            return record.get("mileage_arai_km_per_kg")
        if fuel == "electric":
            return record.get("claimed_ev_range_km")
        return record.get("mileage_arai_kmpl")
    return record.get(field)


def coverage(wrappers: list[dict[str, Any]], fields: tuple[str, ...] | list[str]) -> dict[str, Any]:
    total = len(wrappers)
    result = {}
    for field in fields:
        count = sum(1 for wrapper in wrappers if is_populated(effective_field(canonical(wrapper), field)))
        result[field] = {"populated_count": count, "total": total, "percentage": round(count / total * 100, 2) if total else 0}
    return result


def validate_outputs(
    source_records: list[dict[str, Any]],
    ready: list[dict[str, Any]],
    nullable: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
) -> dict[str, Any]:
    failures = []
    all_output = ready + nullable + excluded
    source_by_version = {item["version_id"]: item["record"] for item in source_records}
    ready_ids = {version_id_for(wrapper) for wrapper in ready}
    excluded_ids = {version_id_for(wrapper) for wrapper in excluded}
    identity_counts = Counter(identity_key(canonical(wrapper)) for wrapper in all_output)
    duplicates = [{"identity": list(key), "count": count} for key, count in identity_counts.items() if count > 1]

    numeric_errors = []
    boolean_errors = []
    implausible = []
    missing_required = []
    unknown_columns = []
    protected_changes = []
    provenance_missing = []

    for wrapper in all_output:
        record = canonical(wrapper)
        version_id = version_id_for(wrapper)
        schema_check = validate_schema_columns(record)
        if schema_check["unknown_columns"]:
            unknown_columns.append({"version_id": version_id, "unknown_columns": schema_check["unknown_columns"]})
        missing = [field for field in REQUIRED_COLUMNS if not is_populated(record.get(field))]
        if missing:
            missing_required.append({"version_id": version_id, "missing_required": missing})
        for field in NUMERIC_COLUMNS:
            value = record.get(field)
            if value not in (None, "") and as_float(value) is None:
                numeric_errors.append({"version_id": version_id, "field": field, "value": value})
        for field in BOOLEAN_COLUMNS:
            if record.get(field) not in (None, True, False):
                boolean_errors.append({"version_id": version_id, "field": field, "value": record.get(field)})
        fuel = str(record.get("fuel_type") or "").lower()
        engine = as_float(record.get("engine_cc"))
        if fuel == "electric" and record.get("engine_cc") is not None:
            implausible.append({"version_id": version_id, "field": "engine_cc", "issue": "EV has engine_cc"})
        if fuel != "electric" and engine is not None and not (600 <= engine <= 6000):
            implausible.append({"version_id": version_id, "field": "engine_cc", "value": record.get("engine_cc")})
        if fuel == "electric" and (record.get("mileage_arai_kmpl") is not None or record.get("mileage_arai_km_per_kg") is not None):
            implausible.append({"version_id": version_id, "field": "mileage", "issue": "EV mileage contamination"})
        if fuel == "cng" and record.get("mileage_arai_kmpl") is not None:
            implausible.append({"version_id": version_id, "field": "mileage_arai_kmpl", "issue": "CNG km/kg in km/l field"})
        source = source_by_version.get(version_id)
        if source:
            for field in PROTECTED_FIELDS:
                if record.get(field) != source.get(field):
                    protected_changes.append({"version_id": version_id, "field": field, "before": source.get(field), "after": record.get(field)})
        for field, provenance in (wrapper.get("final_dataset_resolution_provenance") or {}).items():
            if not provenance.get("source_url") or not provenance.get("raw_value"):
                provenance_missing.append({"version_id": version_id, "field": field, "provenance": provenance})

    quarantined_or_rejected_in_ready = sorted(ready_ids & excluded_ids)
    if duplicates:
        failures.append("duplicate canonical identities")
    if missing_required:
        failures.append("missing required fields")
    if numeric_errors:
        failures.append("numeric type errors")
    if boolean_errors:
        failures.append("boolean type errors")
    if implausible:
        failures.append("implausible values")
    if protected_changes:
        failures.append("protected field changes")
    if provenance_missing:
        failures.append("missing resolution provenance")
    if quarantined_or_rejected_in_ready:
        failures.append("excluded record in ready output")
    return {
        "passed": not failures,
        "failures": failures,
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
        "missing_required": missing_required,
        "unknown_columns": unknown_columns,
        "numeric_type_errors": numeric_errors,
        "boolean_type_errors": boolean_errors,
        "implausible_values": implausible,
        "protected_field_changes": protected_changes,
        "provenance_missing": provenance_missing,
        "quarantined_or_rejected_in_ready": quarantined_or_rejected_in_ready,
        "unsafe_inherited_values": [],
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Final Dataset Build Report",
        "",
        f"- Total source records: {report['total_source_records']}",
        f"- Approved record resolutions applied: {report['approved_resolutions_applied']}",
        f"- Field-value resolutions applied: {report['field_value_resolutions_applied']}",
        f"- Recommendation-ready count: {report['recommendation_ready_count']}",
        f"- Nullable-usable count: {report['nullable_usable_count']}",
        f"- Quarantined count: {report['quarantined_count']}",
        f"- Rejected count: {report['rejected_count']}",
        f"- Unresolved conflict count: {report['unresolved_conflict_count']}",
        f"- Duplicate count: {report['duplicate_count']}",
        f"- Expected 125 ready records produced: {report['expected_125_ready_records_produced']}",
        f"- Validation passed: {report['validation']['passed']}",
        "",
        "## Recommendation-Critical Coverage",
        "",
    ]
    for field, stats in report["recommendation_critical_field_coverage"].items():
        lines.append(f"- {field}: {stats['populated_count']}/{stats['total']} ({stats['percentage']}%)")
    if report["validation"]["failures"]:
        lines.extend(["", "## Validation Failures", ""])
        for failure in report["validation"]["failures"]:
            lines.append(f"- {failure}")
    return "\n".join(lines) + "\n"


def validate_existing_outputs() -> dict[str, Any]:
    source_records = load_models()
    ready = read_json(READY_JSON_PATH, [])
    nullable = read_json(NULLABLE_JSON_PATH, [])
    excluded = read_json(EXCLUDED_JSON_PATH, [])
    validation = validate_outputs(source_records, ready, nullable, excluded)
    return {
        "mode": "validate_only",
        "input_root": str(INPUT_ROOT),
        "recommendation_ready_count": len(ready),
        "nullable_usable_count": len(nullable),
        "excluded_count": len(excluded),
        "expected_125_ready_records_produced": len(ready) == 125,
        "outputs_exist": {
            "recommendation_ready_json": READY_JSON_PATH.exists(),
            "nullable_usable_json": NULLABLE_JSON_PATH.exists(),
            "excluded_json": EXCLUDED_JSON_PATH.exists(),
            "recommendation_ready_csv": READY_CSV_PATH.exists(),
            "nullable_usable_csv": NULLABLE_CSV_PATH.exists(),
        },
        "validation": validation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build final audited canonical recommendation datasets.")
    parser.add_argument("--validate-only", action="store_true", help="Validate existing processed outputs without rewriting them.")
    args = parser.parse_args()

    if args.validate_only:
        result = validate_existing_outputs()
        result["validation_passed"] = result["validation"]["passed"] and all(result["outputs_exist"].values())
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["validation_passed"] else 1)

    source_records = load_models()
    records = deepcopy(source_records)
    review = read_json(REVIEW_PATH, {})
    applied_at = utc_now_iso()
    applied_accept = apply_accept_after_review(records, review, applied_at)
    applied_engine = apply_engine_resolutions(records, review, applied_at)
    conflict_metadata = apply_conflict_metadata(records)
    ready, nullable, excluded = subset_records(records, review)

    write_json(READY_JSON_PATH, ready)
    write_json(NULLABLE_JSON_PATH, nullable)
    write_json(EXCLUDED_JSON_PATH, excluded)
    write_csv(READY_CSV_PATH, ready)
    write_csv(NULLABLE_CSV_PATH, nullable)

    applied_resolutions = {
        "applied_at": applied_at,
        "accept_after_review_field_resolutions": applied_accept,
        "engine_cc_resolutions": applied_engine,
        "unresolved_conflict_metadata": conflict_metadata,
    }
    write_json(APPLIED_RESOLUTIONS_PATH, applied_resolutions)

    validation = validate_outputs(source_records, ready, nullable, excluded)
    quarantined_count = sum(1 for wrapper in excluded if ((wrapper.get("final_dataset_status") or {}).get("decision") or {}).get("decision") == "quarantine")
    rejected_count = sum(1 for wrapper in excluded if ((wrapper.get("final_dataset_status") or {}).get("decision") or {}).get("decision") == "reject")
    report = {
        "input_root": str(INPUT_ROOT),
        "total_source_records": len(source_records),
        "approved_resolutions_applied": len({item["version_id"] for item in applied_accept}),
        "field_value_resolutions_applied": len(applied_accept) + len(applied_engine),
        "approved_record_decisions_applied": len({item["version_id"] for item in applied_accept}),
        "engine_cc_resolutions_applied": len(applied_engine),
        "recommendation_ready_count": len(ready),
        "nullable_usable_count": len(nullable),
        "quarantined_count": quarantined_count,
        "rejected_count": rejected_count,
        "excluded_count": len(excluded),
        "unresolved_conflict_count": len(conflict_metadata),
        "conflict_policy": "canonical values kept; unresolved source conflict metadata attached; conflict-free mileage is not required by current strict active-app readiness",
        "duplicate_count": validation["duplicate_count"],
        "required_field_coverage": coverage(ready, list(REQUIRED_COLUMNS)),
        "recommendation_critical_field_coverage": coverage(ready, list(RECOMMENDATION_CRITICAL_FIELDS)),
        "validation": validation,
        "expected_125_ready_records_produced": len(ready) == 125,
        "outputs": {
            "recommendation_ready_json": str(READY_JSON_PATH),
            "nullable_usable_json": str(NULLABLE_JSON_PATH),
            "excluded_json": str(EXCLUDED_JSON_PATH),
            "recommendation_ready_csv": str(READY_CSV_PATH),
            "nullable_usable_csv": str(NULLABLE_CSV_PATH),
        },
        "supporting_inputs": {
            "remaining_record_review": str(REVIEW_PATH),
            "quarantined_records": str(QUARANTINE_PATH),
            "manual_review_required": str(MANUAL_REVIEW_PATH),
            "mileage_conflict_review": str(MILEAGE_CONFLICT_PATH),
            "engine_cc_repair_report": str(ENGINE_REPAIR_REPORT_PATH),
        },
    }
    write_json(REPORT_JSON_PATH, report)
    REPORT_MD_PATH.write_text(build_markdown(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "total_source_records": report["total_source_records"],
                "approved_resolutions_applied": report["approved_resolutions_applied"],
                "recommendation_ready_count": report["recommendation_ready_count"],
                "nullable_usable_count": report["nullable_usable_count"],
                "excluded_count": report["excluded_count"],
                "unresolved_conflict_count": report["unresolved_conflict_count"],
                "validation_passed": report["validation"]["passed"],
                "expected_125_ready_records_produced": report["expected_125_ready_records_produced"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
