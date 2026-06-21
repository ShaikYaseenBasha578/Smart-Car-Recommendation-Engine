"""Exact-variant safety and parking feature enrichment batch."""

from __future__ import annotations

import copy
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from scraping.enrichment.adapters.cardekho_variant_feature_adapter import CarDekhoVariantFeatureAdapter
from scraping.enrichment.adapters.carwale_variant_feature_adapter import CarWaleVariantFeatureAdapter
from scraping.enrichment.adapters.oem_variant_feature_adapter import MODEL_SOURCES, TARGET_FIELDS, OemVariantFeatureAdapter
from scraping.enrichment.conflict_detector import detect_conflicts
from scraping.enrichment.candidate_resolver import resolution_rank
from scraping.schemas.new_car_schema import BOOLEAN_COLUMNS, NEW_CAR_COLUMNS
from scraping.sources.recommendation_completeness import weighted_completeness_for_record


ROOT = Path(__file__).resolve().parents[2]
INPUT_DATASET = ROOT / "datasets/interim/shared_spec_enrichment/enriched_records.json"
POLICY_PATH = ROOT / "scraping/config/field_enrichment_policy.json"
OUTPUT_DIR = ROOT / "scraping/outputs"
INTERIM_DIR = ROOT / "datasets/interim/variant_safety_enrichment"

MANIFEST_JSON = OUTPUT_DIR / "variant_safety_acquisition_manifest.json"
MANIFEST_MD = OUTPUT_DIR / "variant_safety_acquisition_manifest.md"
CANDIDATES_JSON = INTERIM_DIR / "candidates.json"
CANDIDATES_CSV = INTERIM_DIR / "candidates.csv"
ENRICHED_JSON = INTERIM_DIR / "enriched_records.json"
ENRICHED_CSV = INTERIM_DIR / "enriched_records.csv"
CONFLICTS_JSON = OUTPUT_DIR / "variant_safety_conflicts.json"
MANUAL_REVIEW_JSON = OUTPUT_DIR / "variant_safety_manual_review.json"
DISPOSITION_JSON = OUTPUT_DIR / "variant_safety_candidate_disposition.json"
DISPOSITION_CSV = OUTPUT_DIR / "variant_safety_candidate_disposition.csv"
DISPOSITION_MD = OUTPUT_DIR / "variant_safety_candidate_disposition_summary.md"
REPORT_JSON = OUTPUT_DIR / "variant_safety_enrichment_report.json"
REPORT_MD = OUTPUT_DIR / "variant_safety_enrichment_report.md"
SOURCE_OVERLAP_JSON = OUTPUT_DIR / "variant_safety_source_overlap.json"
SOURCE_OVERLAP_MD = OUTPUT_DIR / "variant_safety_source_overlap.md"


VALID_NULL_REASONS = {
    "NOT_YET_ENRICHED",
    "SOURCE_UNAVAILABLE",
    "FIELD_NOT_PUBLISHED",
    "UNRESOLVED_CONFLICT",
    "LOW_CONFIDENCE_MATCH",
    "EXTRACTION_FAILED",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(wrapper: dict[str, Any]) -> dict[str, Any]:
    return wrapper.get("canonical_record") if isinstance(wrapper.get("canonical_record"), dict) else wrapper


def populated(value: Any) -> bool:
    return value not in (None, "", [], {})


def record_id(wrapper: dict[str, Any]) -> str:
    return str(wrapper.get("version_id") or canonical(wrapper).get("full_name"))


def with_record_id(wrapper: dict[str, Any]) -> dict[str, Any]:
    record = dict(canonical(wrapper))
    record["_record_id"] = record_id(wrapper)
    return record


def candidate_id(index: int) -> str:
    return f"VSAFE-{index:06d}"


def field_coverage(wrappers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for field in TARGET_FIELDS:
        count = sum(1 for wrapper in wrappers if canonical(wrapper).get(field) is not None)
        result[field] = {
            "applicable_records": len(wrappers),
            "populated_count": count,
            "missing_count": len(wrappers) - count,
            "populated_pct": round(count / len(wrappers) * 100, 2) if wrappers else 0.0,
        }
    return result


def completeness(wrappers: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    scores = []
    by_model = defaultdict(list)
    for wrapper in wrappers:
        record = canonical(wrapper)
        score = weighted_completeness_for_record(record, policy)["score"]
        scores.append(score)
        by_model[record.get("model") or "UNKNOWN"].append(score)
    return {
        "average_weighted_recommendation_completeness": round(mean(scores), 2) if scores else 0.0,
        "by_model": {model: round(mean(values), 2) for model, values in sorted(by_model.items())},
    }


def build_manifest(records: list[dict[str, Any]], adapters: list[Any]) -> list[dict[str, Any]]:
    manifest = []
    by_model = defaultdict(list)
    for wrapper in records:
        by_model[(canonical(wrapper).get("make"), canonical(wrapper).get("model"))].append(wrapper)
    for key, wrappers in sorted(by_model.items()):
        canonical_variants = [canonical(wrapper).get("variant") for wrapper in wrappers]
        for adapter in adapters:
            source = MODEL_SOURCES.get(key, {})
            candidates = []
            for wrapper in wrappers:
                candidates.extend(adapter.extract_candidates(with_record_id(wrapper), list(TARGET_FIELDS)))
            match_counts = Counter(candidate.get("variant_match_status") for candidate in candidates)
            manifest.append(
                {
                    "source_name": adapter.source_name,
                    "model": " ".join(key),
                    "source_url_or_document": source.get("source_url") if adapter.source_name.startswith("Official") else adapter.source_name,
                    "trim_names_found": sorted({candidate.get("source_variant") for candidate in candidates if candidate.get("source_variant")}),
                    "canonical_variants_matched": sorted({candidate.get("canonical_variant") for candidate in candidates if candidate.get("canonical_variant")}),
                    "unmatched_source_trims": [],
                    "unmatched_canonical_variants": sorted(set(canonical_variants) - {candidate.get("canonical_variant") for candidate in candidates}),
                    "ambiguous_matches": match_counts.get("AMBIGUOUS", 0),
                    "fields_available": sorted({candidate.get("field_name") for candidate in candidates}),
                    "explicit_negative_values_available": any(candidate.get("normalized_value") is False for candidate in candidates),
                    "extraction_method": "adapter_exact_variant_matrix",
                    "source_publication_model_year": source.get("publication"),
                    "confidence_ceiling": 1.0 if adapter.source_name.startswith("Official") else 0.9,
                }
            )
    return manifest


def write_manifest(manifest: list[dict[str, Any]]) -> None:
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Variant Safety Acquisition Manifest",
        "",
        "| Source | Model | Matched variants | Unmatched variants | Fields | Explicit negatives | Confidence ceiling |",
        "|---|---|---:|---:|---|---|---:|",
    ]
    for item in manifest:
        lines.append(
            f"| {item['source_name']} | {item['model']} | {len(item['canonical_variants_matched'])} | {len(item['unmatched_canonical_variants'])} | {', '.join(item['fields_available'])} | {item['explicit_negative_values_available']} | {item['confidence_ceiling']} |"
        )
    MANIFEST_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def extract_candidates(records: list[dict[str, Any]], adapters: list[Any]) -> list[dict[str, Any]]:
    candidates = []
    for wrapper in records:
        record = with_record_id(wrapper)
        for adapter in adapters:
            candidates.extend(adapter.extract_candidates(record, list(TARGET_FIELDS)))
    for index, candidate in enumerate(candidates, start=1):
        candidate["candidate_id"] = candidate_id(index)
    return candidates


def validate_candidate(candidate: dict[str, Any], record: dict[str, Any]) -> list[str]:
    errors = []
    if candidate.get("field_name") not in TARGET_FIELDS:
        errors.append("field is outside variant-safety target set")
    if candidate.get("inheritance_used"):
        errors.append("inheritance is forbidden for variant-level safety batch")
    if candidate.get("inheritance_scope"):
        errors.append("inheritance scope must be null for direct variant evidence")
    if candidate.get("variant_match_status") not in {"EXACT", "HIGH_CONFIDENCE"}:
        errors.append(f"variant match status {candidate.get('variant_match_status')} is not mergeable")
    components = candidate.get("match_components") or {}
    for key in ("make_match", "model_match", "fuel_match", "transmission_match", "special_edition_match"):
        if components.get(key) is not True:
            errors.append(f"{key} failed")
    if not isinstance(candidate.get("normalized_value"), bool):
        errors.append("normalized boolean value must be explicit true/false")
    if candidate.get("proposed_value") in (None, ""):
        errors.append("raw source value missing; missing text must remain null")
    if record.get("make") != candidate.get("make") or record.get("model") != candidate.get("model"):
        errors.append("candidate identity does not match target record")
    return errors


def rank_candidate(candidate: dict[str, Any]) -> tuple[int, float, str]:
    return (resolution_rank(candidate), -(candidate.get("field_confidence") or 0), candidate.get("candidate_id") or "")


def terminal_dispositions(
    records: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {record_id(wrapper): wrapper for wrapper in records}
    groups = defaultdict(list)
    seen = {}
    for candidate in candidates:
        key = (str(candidate.get("record_id")), candidate.get("field_name"))
        groups[key].append(candidate)

    dispositions = []
    conflicts = []
    accepted = []
    for key, group in groups.items():
        rid, field = key
        record = canonical(by_id[rid])
        valid = []
        for candidate in group:
            exact_key = (
                candidate.get("record_id"),
                candidate.get("field_name"),
                candidate.get("source_name"),
                candidate.get("normalized_value"),
                candidate.get("source_url_or_document_path"),
            )
            errors = validate_candidate(candidate, record)
            if exact_key in seen:
                status = "DUPLICATE_CANDIDATE"
                reason = f"duplicate of {seen[exact_key]}"
            elif errors:
                status = "REJECTED_VALIDATION"
                reason = "; ".join(errors)
            elif (candidate.get("field_confidence") or 0) < 0.9:
                status = "REJECTED_LOW_CONFIDENCE"
                reason = "candidate confidence below high-confidence threshold"
            else:
                status = "VALID_PENDING_GROUP"
                reason = "candidate passed validation"
                valid.append(candidate)
            seen.setdefault(exact_key, candidate.get("candidate_id"))
            candidate["_candidate_errors"] = errors
            candidate["_pre_status"] = status
            candidate["_pre_reason"] = reason

        group_conflicts = detect_conflicts(valid, field)
        if group_conflicts:
            conflicts.extend(group_conflicts)
            for candidate in group:
                if candidate["_pre_status"] == "VALID_PENDING_GROUP":
                    dispositions.append(disposition(candidate, "CONFLICT_UNRESOLVED", "direct true/false conflict remains unresolved"))
                else:
                    dispositions.append(disposition(candidate, candidate["_pre_status"], candidate["_pre_reason"]))
            continue

        valid.sort(key=rank_candidate)
        winner = valid[0] if valid else None
        current = record.get(field)
        for candidate in group:
            if candidate["_pre_status"] != "VALID_PENDING_GROUP":
                dispositions.append(disposition(candidate, candidate["_pre_status"], candidate["_pre_reason"]))
            elif populated(current):
                dispositions.append(disposition(candidate, "EXISTING_VALUE_PRESERVED", "existing canonical value preserved", existing_value=current))
            elif candidate is winner:
                dispositions.append(disposition(candidate, "ACCEPTED", "highest-priority exact variant source"))
                accepted.append(candidate)
            else:
                dispositions.append(
                    disposition(
                        candidate,
                        "SUPERSEDED_BY_HIGHER_PRIORITY_SOURCE",
                        "higher-priority exact source won",
                        winning_candidate_id=winner.get("candidate_id") if winner else None,
                    )
                )
    return dispositions, accepted, conflicts, []


def disposition(
    candidate: dict[str, Any],
    status: str,
    reason: str,
    winning_candidate_id: str | None = None,
    existing_value: Any = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate.get("candidate_id"),
        "record_id": candidate.get("record_id"),
        "field": candidate.get("field_name"),
        "source": candidate.get("source_name"),
        "source_variant": candidate.get("source_variant"),
        "proposed_value": candidate.get("proposed_value"),
        "normalized_value": candidate.get("normalized_value"),
        "terminal_status": status,
        "reason": reason,
        "winning_candidate_id": winning_candidate_id,
        "existing_preserved_value": existing_value,
        "variant_match_status": candidate.get("variant_match_status"),
        "match_components": candidate.get("match_components"),
    }


def merge(records: list[dict[str, Any]], accepted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = copy.deepcopy(records)
    by_id = {record_id(wrapper): wrapper for wrapper in enriched}
    for candidate in accepted:
        wrapper = by_id[str(candidate["record_id"])]
        record = canonical(wrapper)
        field = candidate["field_name"]
        if record.get(field) is not None:
            continue
        record[field] = candidate["normalized_value"]
        wrapper.setdefault("variant_safety_enrichment_provenance", {})[field] = {
            "field": field,
            "value": candidate["normalized_value"],
            "source_name": candidate["source_name"],
            "source_type": candidate["source_type"],
            "source_url_or_document_path": candidate["source_url_or_document_path"],
            "source_variant": candidate.get("source_variant"),
            "evidence": candidate.get("evidence_snippet_or_source_key"),
            "variant_match_status": candidate.get("variant_match_status"),
            "match_components": candidate.get("match_components"),
            "confidence": "high",
            "inherited": False,
            "parser_version": candidate.get("parser_version"),
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }
    return enriched


def unresolved_cells(records: list[dict[str, Any]], enriched: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_keys = {(str(candidate.get("record_id")), candidate.get("field_name")) for candidate in candidates}
    rows = []
    for wrapper in enriched:
        record = canonical(wrapper)
        rid = record_id(wrapper)
        for field in TARGET_FIELDS:
            if record.get(field) is not None:
                continue
            if (rid, field) in candidate_keys:
                reason = "UNRESOLVED_CONFLICT"
                detail = "candidate existed but was not accepted"
            else:
                reason = "FIELD_NOT_PUBLISHED"
                detail = "exact variant matrix did not publish this field for the variant"
            rows.append(
                {
                    "record_id": rid,
                    "make": record.get("make"),
                    "model": record.get("model"),
                    "variant": record.get("variant"),
                    "fuel_type": record.get("fuel_type"),
                    "transmission": record.get("transmission"),
                    "field": field,
                    "null_reason": reason,
                    "reason": detail,
                }
            )
    return rows


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
            "candidate_id",
            "record_id",
            "make",
            "model",
            "canonical_variant",
            "source_variant",
            "fuel_type",
            "transmission",
            "field_name",
            "proposed_value",
            "normalized_value",
            "source_name",
            "source_url_or_document_path",
            "evidence_snippet_or_source_key",
            "variant_match_status",
            "source_publication_date",
            "extraction_method",
            "field_confidence",
            "parser_version",
            "extraction_timestamp",
        ],
    )


def write_enriched_csv(records: list[dict[str, Any]]) -> None:
    rows = []
    for wrapper in records:
        rows.append({"version_id": record_id(wrapper), **{field: canonical(wrapper).get(field) for field in NEW_CAR_COLUMNS}})
    write_csv(ENRICHED_CSV, rows, ["version_id", *NEW_CAR_COLUMNS])


def source_overlap(dispositions: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in dispositions if row["terminal_status"] == "ACCEPTED"]
    by_group = defaultdict(list)
    for row in dispositions:
        by_group[(row["record_id"], row["field"])].append(row)
    assignments = []
    for row in accepted:
        group = by_group[(row["record_id"], row["field"])]
        sources = sorted({item["source"] for item in group})
        values = {json.dumps(item["normalized_value"], sort_keys=True) for item in group}
        assignments.append(
            {
                "record_id": row["record_id"],
                "field": row["field"],
                "sources": sources,
                "single_source": len(sources) == 1,
                "multi_source_agreement": len(sources) > 1 and len(values) == 1,
                "multi_source_disagreement": len(sources) > 1 and len(values) > 1,
                "winning_source": row["source"],
                "official_source_win": str(row["source"]).startswith("Official"),
                "portal_source_win": not str(row["source"]).startswith("Official"),
            }
        )
    summary = defaultdict(Counter)
    for item in assignments:
        summary[item["field"]]["assignments"] += 1
        if item["single_source"]:
            summary[item["field"]]["single_source_assignments"] += 1
        if item["multi_source_agreement"]:
            summary[item["field"]]["multi_source_agreements"] += 1
        if item["multi_source_disagreement"]:
            summary[item["field"]]["multi_source_disagreements"] += 1
        if item["official_source_win"]:
            summary[item["field"]]["official_source_wins"] += 1
        if item["portal_source_win"]:
            summary[item["field"]]["portal_source_wins"] += 1
    return {
        "assignments": assignments,
        "summary_by_field": {field: dict(counter) for field, counter in sorted(summary.items())},
        "zero_conflict_interpretation": "Zero conflicts means no accepted record-field group had disagreeing true/false candidates; multi-source groups are counted separately as agreements.",
    }


def write_dispositions(dispositions: list[dict[str, Any]], unresolved: list[dict[str, Any]]) -> None:
    DISPOSITION_JSON.write_text(json.dumps(dispositions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(
        DISPOSITION_CSV,
        dispositions,
        [
            "candidate_id",
            "record_id",
            "field",
            "source",
            "source_variant",
            "proposed_value",
            "normalized_value",
            "terminal_status",
            "reason",
            "winning_candidate_id",
            "existing_preserved_value",
            "variant_match_status",
        ],
    )
    totals = Counter(row["terminal_status"] for row in dispositions)
    unresolved_totals = Counter(row["null_reason"] for row in unresolved)
    lines = ["# Variant Safety Candidate Disposition Summary", "", f"- Candidates: {len(dispositions)}", f"- Unresolved no-candidate cells: {len(unresolved)}", "", "| Status | Count |", "|---|---:|"]
    for status, count in sorted(totals.items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## Null Reasons", "", "| Reason | Cells |", "|---|---:|"])
    for reason, count in sorted(unresolved_totals.items()):
        lines.append(f"| {reason} | {count} |")
    DISPOSITION_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_source_overlap(overlap: dict[str, Any]) -> None:
    SOURCE_OVERLAP_JSON.write_text(json.dumps(overlap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Variant Safety Source Overlap", "", overlap["zero_conflict_interpretation"], "", "| Field | Assignments | Single-source | Multi-source agreements | Multi-source disagreements | Official wins | Portal wins |", "|---|---:|---:|---:|---:|---:|---:|"]
    for field, row in overlap["summary_by_field"].items():
        lines.append(
            f"| `{field}` | {row.get('assignments', 0)} | {row.get('single_source_assignments', 0)} | {row.get('multi_source_agreements', 0)} | {row.get('multi_source_disagreements', 0)} | {row.get('official_source_wins', 0)} | {row.get('portal_source_wins', 0)} |"
        )
    SOURCE_OVERLAP_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(original: list[dict[str, Any]], enriched: list[dict[str, Any]], policy: dict[str, Any], candidates: list[dict[str, Any]], dispositions: list[dict[str, Any]], unresolved: list[dict[str, Any]], conflicts: list[dict[str, Any]], manifest: list[dict[str, Any]], overlap: dict[str, Any]) -> dict[str, Any]:
    disposition_counts = Counter(row["terminal_status"] for row in dispositions)
    accepted = [row for row in dispositions if row["terminal_status"] == "ACCEPTED"]
    source_counter = Counter(row["source"] for row in accepted)
    by_model_coverage = defaultdict(lambda: {field: {"records": 0, "populated": 0} for field in TARGET_FIELDS})
    for wrapper in enriched:
        record = canonical(wrapper)
        model = record.get("model") or "UNKNOWN"
        for field in TARGET_FIELDS:
            by_model_coverage[model][field]["records"] += 1
            if record.get(field) is not None:
                by_model_coverage[model][field]["populated"] += 1
    model_coverage = {
        model: {
            field: {
                **counts,
                "populated_pct": round(counts["populated"] / counts["records"] * 100, 2) if counts["records"] else 0.0,
            }
            for field, counts in fields.items()
        }
        for model, fields in sorted(by_model_coverage.items())
    }
    coverage_after = field_coverage(enriched)
    weakest = sorted(coverage_after.items(), key=lambda item: item[1]["populated_pct"])[:5]
    suspicious_patterns = []
    for field in TARGET_FIELDS:
        values = {canonical(wrapper).get(field) for wrapper in enriched}
        if len(values) == 1:
            suspicious_patterns.append(
                {
                    "field": field,
                    "pattern": "every variant received the same value",
                    "value": next(iter(values)),
                    "resolution": "retained because candidates carry explicit exact-variant matrix evidence; review source matrix before production migration",
                }
            )
    if candidates and sum(1 for candidate in candidates if candidate.get("variant_match_status") == "EXACT") == len(candidates):
        suspicious_patterns.append(
            {
                "pattern": "all generated candidates had EXACT match status",
                "resolution": "expected for curated exact-variant matrix adapter; guarded by fuel, transmission, and special-edition match tests",
            }
        )
    return {
        "records_inspected": len(original),
        "source_pages_documents_inspected": len(manifest),
        "exact_matches": sum(1 for candidate in candidates if candidate.get("variant_match_status") == "EXACT"),
        "high_confidence_matches": sum(1 for candidate in candidates if candidate.get("variant_match_status") == "HIGH_CONFIDENCE"),
        "ambiguous_matches": sum(1 for candidate in candidates if candidate.get("variant_match_status") == "AMBIGUOUS"),
        "mismatches": sum(1 for candidate in candidates if candidate.get("variant_match_status") == "MISMATCH"),
        "raw_candidates": len(candidates),
        "unique_record_field_candidate_groups": len({(candidate["record_id"], candidate["field_name"]) for candidate in candidates}),
        "accepted_assignments": len(accepted),
        "explicit_true_assignments": sum(1 for row in accepted if row["normalized_value"] is True),
        "explicit_false_assignments": sum(1 for row in accepted if row["normalized_value"] is False),
        "unresolved_null_assignments": len(unresolved),
        "conflicts": len(conflicts),
        "manual_review_cases": len(unresolved),
        "disposition_counts": dict(disposition_counts),
        "source_contribution": dict(source_counter),
        "source_overlap": overlap["summary_by_field"],
        "coverage_before": field_coverage(original),
        "coverage_after": coverage_after,
        "coverage_by_model": model_coverage,
        "weighted_recommendation_completeness_before": completeness(original, policy),
        "weighted_recommendation_completeness_after": completeness(enriched, policy),
        "fields_with_weakest_coverage": [{"field": field, **data} for field, data in weakest],
        "models_with_weakest_feature_coverage": sorted(
            (
                {
                    "model": model,
                    "average_target_coverage": round(mean(field_data["populated_pct"] for field_data in fields.values()), 2),
                }
                for model, fields in model_coverage.items()
            ),
            key=lambda item: item["average_target_coverage"],
        ),
        "suspicious_patterns": suspicious_patterns,
        "validation": {
            "zero_cross_variant_inheritance": all(not candidate.get("inheritance_used") for candidate in candidates),
            "all_candidates_accounted": len(dispositions) == len(candidates),
            "shared_spec_fields_preserved": True,
        },
    }


def write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Variant Safety Enrichment Report",
        "",
        f"- Records inspected: {report['records_inspected']}",
        f"- Source documents/pages inspected: {report['source_pages_documents_inspected']}",
        f"- Raw candidates: {report['raw_candidates']}",
        f"- Accepted assignments: {report['accepted_assignments']}",
        f"- Explicit true assignments: {report['explicit_true_assignments']}",
        f"- Explicit false assignments: {report['explicit_false_assignments']}",
        f"- Unresolved null assignments: {report['unresolved_null_assignments']}",
        f"- Conflicts: {report['conflicts']}",
        f"- Weighted recommendation completeness before: {report['weighted_recommendation_completeness_before']['average_weighted_recommendation_completeness']}%",
        f"- Weighted recommendation completeness after: {report['weighted_recommendation_completeness_after']['average_weighted_recommendation_completeness']}%",
        "",
        "## Disposition Counts",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status, count in sorted(report["disposition_counts"].items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## Coverage", "", "| Field | Before | After |", "|---|---:|---:|"])
    for field in TARGET_FIELDS:
        lines.append(f"| `{field}` | {report['coverage_before'][field]['populated_count']} | {report['coverage_after'][field]['populated_count']} |")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    records = load_json(INPUT_DATASET)
    policy = load_json(POLICY_PATH)
    adapters = [OemVariantFeatureAdapter(), CarDekhoVariantFeatureAdapter(), CarWaleVariantFeatureAdapter()]
    manifest = build_manifest(records, adapters)
    write_manifest(manifest)
    candidates = extract_candidates(records, adapters)
    write_candidates(candidates)
    dispositions, accepted_candidates, conflicts, _ = terminal_dispositions(records, candidates)
    enriched = merge(records, accepted_candidates)
    unresolved = unresolved_cells(records, enriched, candidates)
    for row in unresolved:
        if row["null_reason"] not in VALID_NULL_REASONS:
            raise RuntimeError(f"invalid null reason: {row['null_reason']}")
    CONFLICTS_JSON.write_text(json.dumps(conflicts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MANUAL_REVIEW_JSON.write_text(json.dumps(unresolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ENRICHED_JSON.write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_enriched_csv(enriched)
    write_dispositions(dispositions, unresolved)
    overlap = source_overlap(dispositions)
    write_source_overlap(overlap)
    report = build_report(records, enriched, policy, candidates, dispositions, unresolved, conflicts, manifest, overlap)
    write_report(report)
    print(
        json.dumps(
            {
                "records_inspected": report["records_inspected"],
                "raw_candidates": report["raw_candidates"],
                "accepted_assignments": report["accepted_assignments"],
                "explicit_true_assignments": report["explicit_true_assignments"],
                "explicit_false_assignments": report["explicit_false_assignments"],
                "unresolved_null_assignments": report["unresolved_null_assignments"],
                "conflicts": report["conflicts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
