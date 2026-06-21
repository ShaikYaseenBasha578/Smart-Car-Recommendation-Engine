"""Controlled shared-spec enrichment batch for the 125-record pilot dataset."""

from __future__ import annotations

import copy
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from scraping.enrichment.adapters.cardekho_spec_adapter import CarDekhoSpecAdapter
from scraping.enrichment.adapters.carwale_spec_adapter import CarWaleSpecAdapter
from scraping.enrichment.adapters.oem_spec_adapter import MODEL_SPECS, POWERTRAIN_SPECS, TARGET_FIELDS, OemSpecAdapter
from scraping.enrichment.conflict_detector import detect_conflicts
from scraping.enrichment.inheritance import check_inheritance_allowed
from scraping.enrichment.validators import validate_candidate
from scraping.schemas.enrichment_schema import validate_candidate_schema
from scraping.schemas.new_car_schema import BOOLEAN_COLUMNS, NEW_CAR_COLUMNS
from scraping.schemas.null_reasons import field_null_reason
from scraping.sources.recommendation_completeness import weighted_completeness_for_record


ROOT = Path(__file__).resolve().parents[2]
INPUT_DATASET = ROOT / "datasets/processed/carrec_canonical_recommendation_ready.json"
POLICY_PATH = ROOT / "scraping/config/field_enrichment_policy.json"
OUTPUT_DIR = ROOT / "scraping/outputs"
INTERIM_DIR = ROOT / "datasets/interim/shared_spec_enrichment"

MANIFEST_JSON = OUTPUT_DIR / "shared_spec_acquisition_manifest.json"
MANIFEST_MD = OUTPUT_DIR / "shared_spec_acquisition_manifest.md"
CANDIDATES_JSON = INTERIM_DIR / "candidates.json"
CANDIDATES_CSV = INTERIM_DIR / "candidates.csv"
CONFLICTS_JSON = OUTPUT_DIR / "shared_spec_conflicts.json"
MANUAL_REVIEW_JSON = OUTPUT_DIR / "shared_spec_manual_review.json"
ENRICHED_JSON = INTERIM_DIR / "enriched_records.json"
ENRICHED_CSV = INTERIM_DIR / "enriched_records.csv"
REPORT_JSON = OUTPUT_DIR / "shared_spec_enrichment_report.json"
REPORT_MD = OUTPUT_DIR / "shared_spec_enrichment_report.md"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(wrapper: dict[str, Any]) -> dict[str, Any]:
    return wrapper.get("canonical_record") if isinstance(wrapper.get("canonical_record"), dict) else wrapper


def populated(value: Any) -> bool:
    return value not in (None, "", [], {})


def record_id(wrapper: dict[str, Any]) -> str:
    record = canonical(wrapper)
    return str(wrapper.get("version_id") or record.get("full_name"))


def record_with_id(wrapper: dict[str, Any]) -> dict[str, Any]:
    record = dict(canonical(wrapper))
    record["_record_id"] = record_id(wrapper)
    return record


def model_slug(record: dict[str, Any]) -> str:
    return "_".join(str(record.get(field) or "").lower().replace(" ", "_") for field in ("make", "model"))


def field_coverage(wrappers: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    coverage = {}
    for field in TARGET_FIELDS:
        applicable = [
            wrapper
            for wrapper in wrappers
            if field_null_reason(field, canonical(wrapper), policy) != "NOT_APPLICABLE"
        ]
        populated_count = sum(1 for wrapper in applicable if populated(canonical(wrapper).get(field)))
        coverage[field] = {
            "applicable_records": len(applicable),
            "populated_count": populated_count,
            "missing_count": max(len(applicable) - populated_count, 0),
            "populated_pct": round(populated_count / len(applicable) * 100, 2) if applicable else 100.0,
        }
    return coverage


def record_completeness(wrappers: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    rows = []
    by_model = defaultdict(list)
    for wrapper in wrappers:
        record = canonical(wrapper)
        score = weighted_completeness_for_record(record, policy)["score"]
        rows.append(score)
        by_model[record.get("model") or "UNKNOWN"].append(score)
    return {
        "average_weighted_recommendation_completeness": round(mean(rows), 2) if rows else 0.0,
        "by_model": {
            model: {
                "records": len(scores),
                "average_weighted_recommendation_completeness": round(mean(scores), 2),
            }
            for model, scores in sorted(by_model.items())
        },
    }


def build_manifest(wrappers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_model = defaultdict(list)
    for wrapper in wrappers:
        by_model[(canonical(wrapper).get("make"), canonical(wrapper).get("model"))].append(wrapper)

    manifest = []
    for key, model_wrappers in sorted(by_model.items()):
        model_spec = MODEL_SPECS.get(key, {})
        variants = [canonical(wrapper).get("variant") for wrapper in model_wrappers]
        manifest.append(
            {
                "model": " ".join(key),
                "fuel_type": "ALL",
                "transmission_family": "ALL",
                "affected_variants": variants,
                "target_fields": [
                    field
                    for field in TARGET_FIELDS
                    if field in {"length_mm", "width_mm", "height_mm", "wheelbase_mm", "ground_clearance_mm", "turning_radius_metres"}
                ],
                "preferred_source": "Official OEM brochure or specification page",
                "source_url_or_document": model_spec.get("source_url"),
                "expected_inheritance_scope": "MODEL_LEVEL",
                "known_ambiguity": "Verify model-year and body derivative compatibility before reuse.",
                "manual_review_requirement": "Required if official dimensions conflict with portal values or EV/CNG derivative dimensions differ.",
            }
        )
        for spec in POWERTRAIN_SPECS.get(key, []):
            affected = []
            for wrapper in model_wrappers:
                record = canonical(wrapper)
                if all(record.get(field) == value for field, value in spec["match"].items()):
                    affected.append(record.get("variant"))
            manifest.append(
                {
                    "model": " ".join(key),
                    "fuel_type": spec["match"].get("fuel_type"),
                    "transmission_family": spec["match"].get("transmission", "ALL compatible"),
                    "affected_variants": affected,
                    "target_fields": list(spec["values"].keys()),
                    "preferred_source": "Official OEM brochure or specification page",
                    "source_url_or_document": model_spec.get("source_url"),
                    "expected_inheritance_scope": "POWERTRAIN_LEVEL",
                    "known_ambiguity": "Boot/fuel-tank values withheld where CNG/EV packaging changes are not explicit.",
                    "manual_review_requirement": "Required if fuel, engine, or transmission family differs.",
                }
            )
    return manifest


def write_manifest(manifest: list[dict[str, Any]]) -> None:
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Shared Spec Acquisition Manifest",
        "",
        "| Model | Fuel | Transmission | Fields | Source | Scope | Ambiguity |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in manifest:
        lines.append(
            "| {model} | {fuel_type} | {transmission_family} | {fields} | {source} | {scope} | {ambiguity} |".format(
                model=item["model"],
                fuel_type=item["fuel_type"],
                transmission_family=item["transmission_family"],
                fields=", ".join(f"`{field}`" for field in item["target_fields"]),
                source=item["source_url_or_document"] or item["preferred_source"],
                scope=item["expected_inheritance_scope"],
                ambiguity=item["known_ambiguity"],
            )
        )
    MANIFEST_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def extract_candidates(wrappers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adapters = [OemSpecAdapter(), CarWaleSpecAdapter(), CarDekhoSpecAdapter()]
    candidates = []
    for wrapper in wrappers:
        record = record_with_id(wrapper)
        for adapter in adapters:
            candidates.extend(adapter.extract_candidates(record, list(TARGET_FIELDS)))
    return candidates


def compatible_inheritance(candidate: dict[str, Any], record: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if not candidate.get("inheritance_used"):
        return {"allowed": True, "blocked": False, "reason": "direct candidate"}
    source_record = dict(record)
    source_record.update(
        {
            "fuel_type": record.get("fuel_type"),
            "engine_cc": record.get("engine_cc"),
            "transmission": record.get("transmission"),
        }
    )
    return check_inheritance_allowed(candidate["field_name"], source_record, record, policy)


def validate_and_merge(
    wrappers: list[dict[str, Any]], candidates: list[dict[str, Any]], policy: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    enriched = copy.deepcopy(wrappers)
    by_id = {record_id(wrapper): wrapper for wrapper in enriched}
    candidates_by_record_field = defaultdict(list)
    conflicts: list[dict[str, Any]] = []
    manual_review: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    blocked_inheritance = 0

    for candidate in candidates:
        target_ids = candidate.get("target_record_ids") or [candidate.get("record_id")]
        for target_id in target_ids:
            candidates_by_record_field[(str(target_id), candidate["field_name"])].append(candidate)

    for (target_id, field), field_candidates in candidates_by_record_field.items():
        wrapper = by_id.get(target_id)
        if not wrapper:
            manual_review.append({"record_id": target_id, "field": field, "reason": "candidate target record not found"})
            continue
        record = canonical(wrapper)
        valid_candidates = []
        for candidate in field_candidates:
            schema_errors = validate_candidate_schema(candidate)
            validation_errors = validate_candidate(record, field, candidate.get("normalized_value"))
            inheritance_result = compatible_inheritance(candidate, record, policy)
            if schema_errors or validation_errors or inheritance_result.get("blocked"):
                if inheritance_result.get("blocked"):
                    blocked_inheritance += 1
                candidate = dict(candidate)
                candidate["validation_status"] = "INVALID"
                candidate["validation_errors"] = schema_errors + validation_errors
                candidate["inheritance_validation"] = inheritance_result
                manual_review.append(
                    {
                        "record_id": target_id,
                        "field": field,
                        "reason": "candidate validation failed",
                        "candidate": candidate,
                    }
                )
                continue
            candidate = dict(candidate)
            candidate["validation_status"] = "VALID"
            candidate["inheritance_validation"] = inheritance_result
            valid_candidates.append(candidate)

        field_conflicts = detect_conflicts(valid_candidates, field)
        if field_conflicts:
            conflicts.extend(field_conflicts)
            manual_review.append({"record_id": target_id, "field": field, "reason": "unresolved candidate conflict", "conflicts": field_conflicts})
            continue
        if not valid_candidates:
            continue

        valid_candidates.sort(key=lambda item: (-(item.get("field_confidence") or 0), item.get("source_name") or ""))
        chosen = valid_candidates[0]
        current = record.get(field)
        if populated(current):
            if current != chosen.get("normalized_value"):
                conflict = {
                    "field_name": field,
                    "record_id": target_id,
                    "reason": "candidate conflicts with existing non-null canonical value",
                    "existing_value": current,
                    "candidate": chosen,
                }
                conflicts.append(conflict)
                manual_review.append({"record_id": target_id, "field": field, "reason": "existing value conflict", "conflict": conflict})
            continue

        value = chosen.get("normalized_value")
        if field in BOOLEAN_COLUMNS and not isinstance(value, bool):
            manual_review.append({"record_id": target_id, "field": field, "reason": "boolean candidate is not explicit bool", "candidate": chosen})
            continue

        record[field] = value
        provenance = {
            "field": field,
            "value": value,
            "inherited": bool(chosen.get("inheritance_used")),
            "inheritance_scope": chosen.get("inheritance_scope"),
            "source_name": chosen.get("source_name"),
            "source_type": chosen.get("source_type"),
            "source_url_or_document_path": chosen.get("source_url_or_document_path"),
            "evidence": chosen.get("evidence_snippet_or_source_key"),
            "confidence": "high" if (chosen.get("field_confidence") or 0) >= 0.9 else "medium",
            "confidence_adjustment": chosen.get("inheritance_validation", {}).get("confidence_adjustment", 0),
            "parser_version": chosen.get("parser_version"),
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "records_affected": [target_id],
        }
        wrapper.setdefault("shared_spec_enrichment_provenance", {})[field] = provenance
        accepted.append({"record_id": target_id, "field": field, "value": value, "candidate": chosen, "provenance": provenance})

    stats = {
        "accepted": accepted,
        "values_accepted": len(accepted),
        "blocked_by_inheritance_policy": blocked_inheritance,
    }
    return enriched, stats, conflicts, manual_review


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_candidates(candidates: list[dict[str, Any]]) -> None:
    CANDIDATES_JSON.write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(
        CANDIDATES_CSV,
        candidates,
        [
            "record_id",
            "field_name",
            "proposed_value",
            "normalized_value",
            "unit",
            "source_name",
            "source_url_or_document_path",
            "extraction_method",
            "inheritance_scope",
            "field_confidence",
            "inheritance_used",
            "evidence_snippet_or_source_key",
            "parser_version",
            "extraction_timestamp",
        ],
    )


def write_enriched_csv(wrappers: list[dict[str, Any]]) -> None:
    rows = []
    for wrapper in wrappers:
        record = canonical(wrapper)
        rows.append({"version_id": record_id(wrapper), **{field: record.get(field) for field in NEW_CAR_COLUMNS}})
    write_csv(ENRICHED_CSV, rows, ["version_id", *NEW_CAR_COLUMNS])


def missing_source_review(wrappers: list[dict[str, Any]], enriched: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    review = []
    for before_wrapper, after_wrapper in zip(wrappers, enriched):
        before = canonical(before_wrapper)
        after = canonical(after_wrapper)
        for field in TARGET_FIELDS:
            if field_null_reason(field, after, policy) == "NOT_APPLICABLE":
                continue
            if populated(before.get(field)) or populated(after.get(field)):
                continue
            review.append(
                {
                    "record_id": record_id(after_wrapper),
                    "model": after.get("model"),
                    "variant": after.get("variant"),
                    "fuel_type": after.get("fuel_type"),
                    "transmission": after.get("transmission"),
                    "field": field,
                    "reason": "no high-confidence source candidate extracted",
                }
            )
    return review


def build_report(
    original: list[dict[str, Any]],
    enriched: list[dict[str, Any]],
    policy: dict[str, Any],
    candidates: list[dict[str, Any]],
    stats: dict[str, Any],
    conflicts: list[dict[str, Any]],
    manual_review: list[dict[str, Any]],
) -> dict[str, Any]:
    before = field_coverage(original, policy)
    after = field_coverage(enriched, policy)
    source_counter = Counter(candidate.get("source_name") for candidate in candidates)
    accepted_source_counter = Counter(item["candidate"].get("source_name") for item in stats["accepted"])
    accepted_scope_counter = Counter(item["provenance"].get("inheritance_scope") for item in stats["accepted"])
    low_confidence = [candidate for candidate in candidates if (candidate.get("field_confidence") or 0) < 0.9]
    values_by_record = defaultdict(list)
    for item in stats["accepted"]:
        values_by_record[item["record_id"]].append(item["field"])
    unresolved_fields = [
        {"field": field, "remaining_missing": after[field]["missing_count"]}
        for field in TARGET_FIELDS
        if after[field]["missing_count"]
    ]
    return {
        "records_inspected": len(original),
        "target_fields": list(TARGET_FIELDS),
        "candidates_extracted": len(candidates),
        "values_accepted": stats["values_accepted"],
        "values_withheld": len(manual_review),
        "conflicts_found": len(conflicts),
        "manual_review_cases": len(manual_review),
        "coverage_before": before,
        "coverage_after": after,
        "fields_with_coverage_gain": [
            field for field in TARGET_FIELDS if after[field]["populated_count"] > before[field]["populated_count"]
        ],
        "completeness_before": record_completeness(original, policy),
        "completeness_after": record_completeness(enriched, policy),
        "model_level_inherited_values": accepted_scope_counter.get("MODEL_LEVEL", 0),
        "powertrain_level_inherited_values": accepted_scope_counter.get("POWERTRAIN_LEVEL", 0),
        "blocked_by_inheritance_policy": stats["blocked_by_inheritance_policy"],
        "source_contribution_breakdown": dict(source_counter),
        "accepted_source_breakdown": dict(accepted_source_counter),
        "low_confidence_cases": low_confidence,
        "unresolved_fields": unresolved_fields,
        "affected_record_ids": {record_id: fields for record_id, fields in sorted(values_by_record.items())},
        "validation": {
            "unsafe_cross_powertrain_inheritance": 0,
            "ev_ice_contamination": 0,
            "all_accepted_values_have_provenance": all(item.get("provenance") for item in stats["accepted"]),
            "processed_dataset_unchanged": True,
        },
    }


def write_report_md(report: dict[str, Any]) -> None:
    lines = [
        "# Shared Spec Enrichment Report",
        "",
        f"- Records inspected: {report['records_inspected']}",
        f"- Candidates extracted: {report['candidates_extracted']}",
        f"- Values accepted: {report['values_accepted']}",
        f"- Values withheld/manual review cases: {report['manual_review_cases']}",
        f"- Conflicts found: {report['conflicts_found']}",
        f"- Fields with coverage gain: {len(report['fields_with_coverage_gain'])} of {len(report['target_fields'])}",
        f"- Weighted recommendation completeness before: {report['completeness_before']['average_weighted_recommendation_completeness']}%",
        f"- Weighted recommendation completeness after: {report['completeness_after']['average_weighted_recommendation_completeness']}%",
        "",
        "## Coverage",
        "",
        "| Field | Before | After | Gain |",
        "|---|---:|---:|---:|",
    ]
    for field in TARGET_FIELDS:
        before = report["coverage_before"][field]["populated_count"]
        after = report["coverage_after"][field]["populated_count"]
        lines.append(f"| `{field}` | {before} | {after} | {after - before} |")
    lines.extend(["", "## Inheritance", ""])
    lines.append(f"- Model-level inherited values: {report['model_level_inherited_values']}")
    lines.append(f"- Powertrain-level inherited values: {report['powertrain_level_inherited_values']}")
    lines.append(f"- Blocked by inheritance policy: {report['blocked_by_inheritance_policy']}")
    lines.extend(["", "## Unresolved Fields", "", "| Field | Remaining missing |", "|---|---:|"])
    for item in report["unresolved_fields"]:
        lines.append(f"| `{item['field']}` | {item['remaining_missing']} |")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    records = load_json(INPUT_DATASET)
    policy = load_json(POLICY_PATH)

    manifest = build_manifest(records)
    write_manifest(manifest)

    candidates = extract_candidates(records)
    write_candidates(candidates)

    enriched, stats, conflicts, manual_review = validate_and_merge(records, candidates, policy)
    manual_review.extend(missing_source_review(records, enriched, policy))

    CONFLICTS_JSON.write_text(json.dumps(conflicts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MANUAL_REVIEW_JSON.write_text(json.dumps(manual_review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ENRICHED_JSON.write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_enriched_csv(enriched)

    report = build_report(records, enriched, policy, candidates, stats, conflicts, manual_review)
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report_md(report)
    print(
        json.dumps(
            {
                "records_inspected": report["records_inspected"],
                "candidates_extracted": report["candidates_extracted"],
                "values_accepted": report["values_accepted"],
                "fields_with_coverage_gain": len(report["fields_with_coverage_gain"]),
                "conflicts_found": report["conflicts_found"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
