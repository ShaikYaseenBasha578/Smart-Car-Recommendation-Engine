"""Reconcile candidate accounting for the completed shared-spec enrichment batch."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scraping.enrichment.conflict_detector import detect_conflicts
from scraping.enrichment.inheritance import check_inheritance_allowed
from scraping.enrichment.validators import validate_candidate
from scraping.schemas.enrichment_schema import validate_candidate_schema
from scraping.schemas.null_reasons import NULL_REASONS
from scraping.sources.shared_spec_enrichment_batch import TARGET_FIELDS, field_coverage, record_completeness


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_PATH = ROOT / "datasets/processed/carrec_canonical_recommendation_ready.json"
CANDIDATES_PATH = ROOT / "datasets/interim/shared_spec_enrichment/candidates.json"
ENRICHED_PATH = ROOT / "datasets/interim/shared_spec_enrichment/enriched_records.json"
REPORT_PATH = ROOT / "scraping/outputs/shared_spec_enrichment_report.json"
REPORT_MD_PATH = ROOT / "scraping/outputs/shared_spec_enrichment_report.md"
MANUAL_REVIEW_PATH = ROOT / "scraping/outputs/shared_spec_manual_review.json"
CONFLICTS_PATH = ROOT / "scraping/outputs/shared_spec_conflicts.json"
POLICY_PATH = ROOT / "scraping/config/field_enrichment_policy.json"

DISPOSITION_JSON = ROOT / "scraping/outputs/shared_spec_candidate_disposition.json"
DISPOSITION_CSV = ROOT / "scraping/outputs/shared_spec_candidate_disposition.csv"
DISPOSITION_MD = ROOT / "scraping/outputs/shared_spec_candidate_disposition_summary.md"
SOURCE_OVERLAP_JSON = ROOT / "scraping/outputs/shared_spec_source_overlap.json"
SOURCE_OVERLAP_MD = ROOT / "scraping/outputs/shared_spec_source_overlap.md"
INHERITANCE_JSON = ROOT / "scraping/outputs/shared_spec_inheritance_audit.json"
INHERITANCE_MD = ROOT / "scraping/outputs/shared_spec_inheritance_audit.md"


TERMINAL_STATUSES = {
    "ACCEPTED",
    "REJECTED_VALIDATION",
    "REJECTED_LOW_CONFIDENCE",
    "REJECTED_SCOPE_MISMATCH",
    "REJECTED_INHERITANCE_POLICY",
    "DUPLICATE_CANDIDATE",
    "SUPERSEDED_BY_HIGHER_PRIORITY_SOURCE",
    "EXISTING_VALUE_PRESERVED",
    "CONFLICT_UNRESOLVED",
    "NOT_APPLICABLE",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(wrapper: dict[str, Any]) -> dict[str, Any]:
    record = wrapper.get("canonical_record")
    return record if isinstance(record, dict) else wrapper


def populated(value: Any) -> bool:
    return value not in (None, "", [], {})


def record_id(wrapper: dict[str, Any]) -> str:
    return str(wrapper.get("version_id") or canonical(wrapper).get("full_name"))


def candidate_id(index: int) -> str:
    return f"SSCAND-{index:06d}"


def build_maps(original: list[dict[str, Any]], enriched: list[dict[str, Any]]) -> tuple[dict[str, dict], dict[str, dict], dict[tuple[str, str], dict]]:
    original_by_id = {record_id(wrapper): wrapper for wrapper in original}
    enriched_by_id = {record_id(wrapper): wrapper for wrapper in enriched}
    provenance_by_record_field = {}
    for wrapper in enriched:
        rid = record_id(wrapper)
        for field, provenance in wrapper.get("shared_spec_enrichment_provenance", {}).items():
            provenance_by_record_field[(rid, field)] = provenance
    return original_by_id, enriched_by_id, provenance_by_record_field


def inheritance_decision(candidate: dict[str, Any], record: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if not candidate.get("inheritance_used"):
        return {"allowed": True, "blocked": False, "reason": "direct exact-record assignment"}
    source_record = dict(record)
    return check_inheritance_allowed(candidate["field_name"], source_record, record, policy)


def classify_candidates(
    candidates: list[dict[str, Any]],
    original_by_id: dict[str, dict],
    enriched_by_id: dict[str, dict],
    provenance_by_record_field: dict[tuple[str, str], dict],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    groups = defaultdict(list)
    rows = []
    seen_exact = {}
    for index, candidate in enumerate(candidates, start=1):
        cid = candidate_id(index)
        candidate = dict(candidate)
        candidate["candidate_id"] = cid
        groups[(str(candidate.get("record_id")), candidate.get("field_name"))].append(candidate)
        exact_key = (
            str(candidate.get("record_id")),
            candidate.get("field_name"),
            candidate.get("source_name"),
            json.dumps(candidate.get("normalized_value"), sort_keys=True),
            candidate.get("source_url_or_document_path"),
        )
        if exact_key in seen_exact:
            candidate["_duplicate_of"] = seen_exact[exact_key]
        else:
            seen_exact[exact_key] = cid
        rows.append(candidate)

    conflict_groups = {}
    for key, group in groups.items():
        conflicts = detect_conflicts(group, key[1])
        if conflicts:
            for conflict_index, _ in enumerate(conflicts, start=1):
                conflict_groups[key] = f"SSCONFLICT-{key[0]}-{key[1]}-{conflict_index}"

    dispositions = []
    for candidate in rows:
        rid = str(candidate.get("record_id"))
        field = candidate.get("field_name")
        original_wrapper = original_by_id.get(rid)
        enriched_wrapper = enriched_by_id.get(rid)
        original = canonical(original_wrapper) if original_wrapper else {}
        enriched = canonical(enriched_wrapper) if enriched_wrapper else {}
        value = candidate.get("normalized_value")
        validation_errors = validate_candidate_schema(candidate) + validate_candidate(original, field, value)
        inheritance = inheritance_decision(candidate, original, policy) if original else {"allowed": False, "blocked": True, "reason": "record not found"}
        terminal_status = None
        reason = None
        winning_id = None
        preserved = None
        conflict_group = conflict_groups.get((rid, field))

        if candidate.get("_duplicate_of"):
            terminal_status = "DUPLICATE_CANDIDATE"
            reason = f"duplicate of {candidate['_duplicate_of']}"
            winning_id = candidate["_duplicate_of"]
        elif conflict_group:
            terminal_status = "CONFLICT_UNRESOLVED"
            reason = "competing candidates disagree"
        elif validation_errors:
            terminal_status = "REJECTED_VALIDATION"
            reason = "; ".join(validation_errors)
        elif inheritance.get("blocked"):
            terminal_status = "REJECTED_INHERITANCE_POLICY"
            reason = inheritance.get("reason")
        elif (candidate.get("field_confidence") or 0) < 0.9:
            terminal_status = "REJECTED_LOW_CONFIDENCE"
            reason = "field confidence below high-confidence acceptance threshold"
        elif populated(original.get(field)):
            terminal_status = "EXISTING_VALUE_PRESERVED"
            preserved = original.get(field)
            reason = "canonical field already contained a non-null value before shared-spec enrichment"
        elif provenance_by_record_field.get((rid, field)) and enriched.get(field) == value:
            terminal_status = "ACCEPTED"
            reason = "candidate value populated the previously missing record-field cell"
        else:
            same_group = groups[(rid, field)]
            accepted_candidates = [
                item
                for item in same_group
                if provenance_by_record_field.get((rid, field))
                and canonical(enriched_by_id[rid]).get(field) == item.get("normalized_value")
            ]
            if accepted_candidates:
                terminal_status = "SUPERSEDED_BY_HIGHER_PRIORITY_SOURCE"
                winning_id = accepted_candidates[0]["candidate_id"]
                reason = "another candidate won deterministic source/confidence ordering"
            else:
                terminal_status = "REJECTED_SCOPE_MISMATCH"
                reason = "candidate did not match an accepted assignment or preserved existing value"

        dispositions.append(
            {
                "candidate_id": candidate["candidate_id"],
                "record_id": rid,
                "field": field,
                "source": candidate.get("source_name"),
                "proposed_value": candidate.get("proposed_value"),
                "normalized_value": value,
                "terminal_status": terminal_status,
                "reason": reason,
                "winning_candidate_id": winning_id,
                "existing_preserved_value": preserved,
                "validation_result": "VALID" if not validation_errors else "INVALID",
                "validation_errors": validation_errors,
                "inheritance_decision": inheritance,
                "conflict_group": conflict_group,
            }
        )
    return dispositions


def classify_unresolved_cells(manual_review: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in manual_review:
        field = item.get("field")
        fuel = str(item.get("fuel_type") or "").lower()
        if field == "kerb_weight_kg":
            null_reason = "FIELD_NOT_PUBLISHED"
            detail = "Reviewed shared sources did not publish variant-safe kerb weight."
        elif field in {"boot_space_litres", "fuel_tank_capacity_litres"} and fuel == "cng":
            null_reason = "UNSAFE_TO_INHERIT"
            detail = "Nearby ICE value exists, but CNG packaging/tank differences block inheritance."
        elif field == "fuel_tank_capacity_litres" and fuel == "electric":
            null_reason = "NOT_APPLICABLE"
            detail = "Fuel tank is not applicable to EV records."
        elif field == "gearbox_speeds":
            null_reason = "SOURCE_UNAVAILABLE"
            detail = "No high-confidence gearbox-speed source candidate was generated for this exact transmission family."
        else:
            null_reason = "SOURCE_UNAVAILABLE"
            detail = "No high-confidence source candidate was generated."
        if null_reason not in NULL_REASONS:
            raise ValueError(f"unsupported null reason {null_reason}")
        rows.append({**item, "null_reason": null_reason, "null_reason_detail": detail})
    return rows


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
                "candidate_sources_available": len(sources),
                "sources": sources,
                "single_source": len(sources) == 1,
                "multiple_sources_agreed": len(sources) > 1 and len(values) == 1,
                "multiple_sources_disagreed": len(sources) > 1 and len(values) > 1,
                "winning_source": row["source"],
                "why_won": "only high-confidence source supplied a candidate" if len(sources) == 1 else "highest deterministic source/confidence rank",
            }
        )

    summary_by_field = defaultdict(Counter)
    summary_by_model_source = defaultdict(Counter)
    for item in assignments:
        summary_by_field[item["field"]]["assignments"] += 1
        if item["single_source"]:
            summary_by_field[item["field"]]["single_source_assignments"] += 1
        if item["multiple_sources_agreed"]:
            summary_by_field[item["field"]]["multi_source_agreements"] += 1
        if item["multiple_sources_disagreed"]:
            summary_by_field[item["field"]]["multi_source_disagreements"] += 1
        summary_by_field[item["field"]][f"source_wins::{item['winning_source']}"] += 1

    for item in assignments:
        summary_by_model_source[(item["field"], item["winning_source"])]["source_wins"] += 1

    return {
        "assignments": assignments,
        "summary_by_field": {field: dict(counter) for field, counter in sorted(summary_by_field.items())},
        "summary_by_field_source": {
            f"{field}|{source}": dict(counter) for (field, source), counter in sorted(summary_by_model_source.items())
        },
        "zero_conflict_interpretation": "Only one adapter/source supplied candidates for accepted assignments, so the zero-conflict result means competing candidates generally did not reach conflict detection in this batch.",
    }


def inheritance_audit(dispositions: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    accepted = [row for row in dispositions if row["terminal_status"] == "ACCEPTED"]
    blocked = [row for row in dispositions if row["terminal_status"] == "REJECTED_INHERITANCE_POLICY"]
    never_generated = classify_unresolved_cells(load_json(MANUAL_REVIEW_PATH))
    scope_counts = Counter(row["inheritance_decision"].get("source_scope") or row["inheritance_decision"].get("target_scope") or "UNKNOWN" for row in accepted)

    test_cases = [
        (
            "petrol_to_diesel",
            "boot_space_litres",
            {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Manual"},
            {"make": "Tata", "model": "Nexon", "fuel_type": "Diesel", "engine_cc": 1497, "transmission": "Manual"},
        ),
        (
            "petrol_to_cng",
            "boot_space_litres",
            {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Manual"},
            {"make": "Tata", "model": "Nexon", "fuel_type": "CNG", "engine_cc": 1199, "transmission": "Manual"},
        ),
        (
            "ice_to_ev",
            "drivetrain",
            {"make": "MG", "model": "Windsor EV", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Manual"},
            {"make": "MG", "model": "Windsor EV", "fuel_type": "Electric", "engine_cc": None, "transmission": "Automatic"},
        ),
        (
            "manual_to_automatic_gearbox",
            "gearbox_speeds",
            {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Manual"},
            {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Automatic (DCT)"},
        ),
        (
            "automatic_gearbox_type_mismatch",
            "gearbox_speeds",
            {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Automatic (AMT)"},
            {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Automatic (DCT)"},
        ),
        (
            "model_dimensions_cross_model",
            "length_mm",
            {"make": "Hyundai", "model": "Creta", "fuel_type": "Petrol"},
            {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol"},
        ),
    ]
    results = []
    for name, field, source, target in test_cases:
        result = check_inheritance_allowed(field, source, target, policy)
        results.append({"case": name, "field": field, "blocked": result.get("blocked"), "decision": result})

    return {
        "inherited_assignments_allowed": len(accepted),
        "candidate_assignments_blocked": len(blocked),
        "candidate_assignments_never_generated_scope_or_source": len(never_generated),
        "model_level_assignments": scope_counts.get("MODEL_LEVEL", 0),
        "powertrain_level_assignments": scope_counts.get("POWERTRAIN_LEVEL", 0),
        "direct_exact_record_assignments": scope_counts.get("direct exact-record assignment", 0),
        "blocked_candidates": blocked,
        "never_generated_examples": never_generated[:50],
        "policy_block_test_cases": results,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_disposition_outputs(dispositions: list[dict[str, Any]], unresolved: list[dict[str, Any]]) -> None:
    DISPOSITION_JSON.write_text(json.dumps(dispositions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MANUAL_REVIEW_PATH.write_text(json.dumps(unresolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(
        DISPOSITION_CSV,
        dispositions,
        [
            "candidate_id",
            "record_id",
            "field",
            "source",
            "proposed_value",
            "normalized_value",
            "terminal_status",
            "reason",
            "winning_candidate_id",
            "existing_preserved_value",
            "validation_result",
            "conflict_group",
        ],
    )
    totals = Counter(row["terminal_status"] for row in dispositions)
    unresolved_totals = Counter(row["null_reason"] for row in unresolved)
    lines = [
        "# Shared Spec Candidate Disposition Summary",
        "",
        f"- Extracted candidates reconciled: {len(dispositions)}",
        f"- Unresolved record-field cells: {len(unresolved)}",
        "",
        "## Candidate Terminal Statuses",
        "",
        "| Status | Candidates |",
        "|---|---:|",
    ]
    for status, count in sorted(totals.items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## Unresolved Cell Null Reasons", "", "| Null reason | Cells |", "|---|---:|"])
    for reason, count in sorted(unresolved_totals.items()):
        lines.append(f"| {reason} | {count} |")
    DISPOSITION_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_source_overlap_outputs(overlap: dict[str, Any]) -> None:
    SOURCE_OVERLAP_JSON.write_text(json.dumps(overlap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Shared Spec Source Overlap Audit",
        "",
        overlap["zero_conflict_interpretation"],
        "",
        "| Field | Assignments | Single-source | Multi-source agreements | Multi-source disagreements |",
        "|---|---:|---:|---:|---:|",
    ]
    for field, item in overlap["summary_by_field"].items():
        lines.append(
            f"| `{field}` | {item.get('assignments', 0)} | {item.get('single_source_assignments', 0)} | {item.get('multi_source_agreements', 0)} | {item.get('multi_source_disagreements', 0)} |"
        )
    SOURCE_OVERLAP_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_inheritance_outputs(audit: dict[str, Any]) -> None:
    INHERITANCE_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Shared Spec Inheritance Audit",
        "",
        f"- Inherited assignments allowed: {audit['inherited_assignments_allowed']}",
        f"- Candidate assignments blocked: {audit['candidate_assignments_blocked']}",
        f"- Candidate assignments never generated because source/scope evidence was unavailable: {audit['candidate_assignments_never_generated_scope_or_source']}",
        f"- Model-level assignments: {audit['model_level_assignments']}",
        f"- Powertrain-level assignments: {audit['powertrain_level_assignments']}",
        f"- Direct exact-record assignments: {audit['direct_exact_record_assignments']}",
        "",
        "## Policy Block Test Cases",
        "",
        "| Case | Field | Blocked | Reason |",
        "|---|---|---|---|",
    ]
    for case in audit["policy_block_test_cases"]:
        lines.append(f"| {case['case']} | `{case['field']}` | {case['blocked']} | {case['decision'].get('reason')} |")
    INHERITANCE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_shared_report(
    original: list[dict[str, Any]],
    enriched: list[dict[str, Any]],
    policy: dict[str, Any],
    dispositions: list[dict[str, Any]],
    unresolved: list[dict[str, Any]],
    overlap: dict[str, Any],
    inheritance: dict[str, Any],
) -> None:
    report = load_json(REPORT_PATH)
    terminal_totals = Counter(row["terminal_status"] for row in dispositions)
    unresolved_totals = Counter(row["null_reason"] for row in unresolved)
    groups = {(row["record_id"], row["field"]) for row in dispositions}
    accepted_groups = {(row["record_id"], row["field"]) for row in dispositions if row["terminal_status"] == "ACCEPTED"}
    report["accounting_reconciliation"] = {
        "raw_candidates_extracted": len(dispositions),
        "unique_record_field_candidate_groups": len(groups),
        "accepted_record_field_assignments": len(accepted_groups),
        "existing_values_preserved": terminal_totals.get("EXISTING_VALUE_PRESERVED", 0),
        "duplicate_candidates": terminal_totals.get("DUPLICATE_CANDIDATE", 0),
        "superseded_candidates": terminal_totals.get("SUPERSEDED_BY_HIGHER_PRIORITY_SOURCE", 0),
        "rejected_candidates": sum(count for status, count in terminal_totals.items() if status.startswith("REJECTED")),
        "unresolved_record_field_cells_no_candidate": len(unresolved),
        "unresolved_conflicts": terminal_totals.get("CONFLICT_UNRESOLVED", 0),
        "candidate_terminal_status_totals": dict(terminal_totals),
        "unresolved_cell_null_reason_totals": dict(unresolved_totals),
    }
    report["source_overlap_summary"] = {
        "zero_conflict_interpretation": overlap["zero_conflict_interpretation"],
        "summary_by_field": overlap["summary_by_field"],
    }
    report["inheritance_policy_summary"] = {
        key: inheritance[key]
        for key in (
            "inherited_assignments_allowed",
            "candidate_assignments_blocked",
            "candidate_assignments_never_generated_scope_or_source",
            "model_level_assignments",
            "powertrain_level_assignments",
            "direct_exact_record_assignments",
        )
    }
    report["coverage_before"] = field_coverage(original, policy)
    report["coverage_after"] = field_coverage(enriched, policy)
    report["completeness_before"] = record_completeness(original, policy)
    report["completeness_after"] = record_completeness(enriched, policy)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Shared Spec Enrichment Report",
        "",
        f"- Records inspected: {report['records_inspected']}",
        f"- Raw candidates extracted: {len(dispositions)}",
        f"- Unique record-field candidate groups: {len(groups)}",
        f"- Accepted record-field assignments: {len(accepted_groups)}",
        f"- Existing values preserved: {terminal_totals.get('EXISTING_VALUE_PRESERVED', 0)}",
        f"- Duplicate candidates: {terminal_totals.get('DUPLICATE_CANDIDATE', 0)}",
        f"- Superseded candidates: {terminal_totals.get('SUPERSEDED_BY_HIGHER_PRIORITY_SOURCE', 0)}",
        f"- Rejected candidates: {report['accounting_reconciliation']['rejected_candidates']}",
        f"- Unresolved record-field cells with no candidate: {len(unresolved)}",
        f"- Unresolved conflicts: {terminal_totals.get('CONFLICT_UNRESOLVED', 0)}",
        f"- Weighted recommendation completeness before: {report['completeness_before']['average_weighted_recommendation_completeness']}%",
        f"- Weighted recommendation completeness after: {report['completeness_after']['average_weighted_recommendation_completeness']}%",
        "",
        "## Candidate Disposition",
        "",
        "| Status | Candidates |",
        "|---|---:|",
    ]
    for status, count in sorted(terminal_totals.items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## Unresolved Cell Reasons", "", "| Null reason | Cells |", "|---|---:|"])
    for reason, count in sorted(unresolved_totals.items()):
        lines.append(f"| {reason} | {count} |")
    lines.extend(["", "## Source Overlap", "", overlap["zero_conflict_interpretation"], "", "| Field | Assignments | Single-source | Multi-source disagreements |", "|---|---:|---:|---:|"])
    for field, item in overlap["summary_by_field"].items():
        lines.append(f"| `{field}` | {item.get('assignments', 0)} | {item.get('single_source_assignments', 0)} | {item.get('multi_source_disagreements', 0)} |")
    lines.extend(["", "## Inheritance Policy", ""])
    for key in (
        "inherited_assignments_allowed",
        "candidate_assignments_blocked",
        "candidate_assignments_never_generated_scope_or_source",
        "model_level_assignments",
        "powertrain_level_assignments",
        "direct_exact_record_assignments",
    ):
        lines.append(f"- {key}: {inheritance[key]}")
    lines.extend(["", "## Coverage", "", "| Field | Before | After | Gain |", "|---|---:|---:|---:|"])
    for field in TARGET_FIELDS:
        before = report["coverage_before"][field]["populated_count"]
        after = report["coverage_after"][field]["populated_count"]
        lines.append(f"| `{field}` | {before} | {after} | {after - before} |")
    REPORT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    original = load_json(ORIGINAL_PATH)
    enriched = load_json(ENRICHED_PATH)
    candidates = load_json(CANDIDATES_PATH)
    manual_review = load_json(MANUAL_REVIEW_PATH)
    policy = load_json(POLICY_PATH)
    original_by_id, enriched_by_id, provenance_by_record_field = build_maps(original, enriched)

    dispositions = classify_candidates(candidates, original_by_id, enriched_by_id, provenance_by_record_field, policy)
    unresolved = classify_unresolved_cells(manual_review)
    overlap = source_overlap(dispositions)
    inheritance = inheritance_audit(dispositions, policy)

    totals = Counter(row["terminal_status"] for row in dispositions)
    if len(dispositions) != len(candidates):
        raise RuntimeError("candidate disposition count does not match extracted candidates")
    unknown = set(totals) - TERMINAL_STATUSES
    if unknown:
        raise RuntimeError(f"unknown terminal statuses: {sorted(unknown)}")
    if sum(totals.values()) != len(candidates):
        raise RuntimeError("terminal status totals do not reconcile")

    write_disposition_outputs(dispositions, unresolved)
    write_source_overlap_outputs(overlap)
    write_inheritance_outputs(inheritance)
    update_shared_report(original, enriched, policy, dispositions, unresolved, overlap, inheritance)
    print(
        json.dumps(
            {
                "candidate_dispositions": len(dispositions),
                "terminal_status_totals": dict(totals),
                "unresolved_cells": len(unresolved),
                "unresolved_null_reasons": dict(Counter(row["null_reason"] for row in unresolved)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
