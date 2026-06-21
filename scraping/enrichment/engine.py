"""Dry-run enrichment engine coordinator."""

from __future__ import annotations

from scraping.enrichment.candidate_resolver import resolve_candidates
from scraping.enrichment.conflict_detector import detect_conflicts
from scraping.enrichment.missing_field_detector import prioritized_enrichment_queue
from scraping.enrichment.validators import validate_candidate


def plan_enrichment(records: list[dict], policy: dict, adapters: list[object] | None = None) -> dict:
    queue = prioritized_enrichment_queue(records, policy)
    return {
        "mode": "dry_run",
        "queue_size": len(queue),
        "next_items": queue[:100],
        "adapters": [adapter.source_metadata() for adapter in adapters or [] if hasattr(adapter, "source_metadata")],
    }


def evaluate_candidates(record: dict, field_name: str, candidates: list[dict]) -> dict:
    for candidate in candidates:
        errors = validate_candidate(record, field_name, candidate.get("normalized_value"))
        candidate["validation_status"] = "VALID" if not errors else "INVALID"
        candidate["validation_errors"] = errors
    conflicts = detect_conflicts(candidates, field_name)
    resolution = resolve_candidates(candidates, conflicts)
    return {"candidates": candidates, "conflicts": conflicts, "resolution": resolution}
