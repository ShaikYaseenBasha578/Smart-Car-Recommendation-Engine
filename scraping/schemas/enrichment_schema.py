"""Schema helpers for enrichment candidates and accepted values."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


CANDIDATE_VALUE_FIELDS = (
    "record_id",
    "field_name",
    "proposed_value",
    "normalized_value",
    "unit",
    "source_name",
    "source_type",
    "source_url_or_document_path",
    "extraction_method",
    "extraction_timestamp",
    "source_publication_date",
    "exact_match_confidence",
    "field_confidence",
    "inheritance_used",
    "inheritance_scope",
    "inherited_from_record_id",
    "evidence_snippet_or_source_key",
    "conflict_group",
    "validation_status",
    "rejection_reason",
    "parser_version",
)

ACCEPTED_VALUE_FIELDS = (
    "final_value",
    "chosen_source",
    "confidence",
    "resolution_method",
    "provenance",
    "inherited",
    "manually_approved",
    "competing_candidates",
    "conflict_status",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def candidate_value(**kwargs: Any) -> dict:
    """Build a normalized candidate-value envelope."""
    candidate = {field: None for field in CANDIDATE_VALUE_FIELDS}
    candidate.update(kwargs)
    candidate.setdefault("extraction_timestamp", utc_now_iso())
    candidate.setdefault("inheritance_used", False)
    candidate.setdefault("validation_status", "UNVALIDATED")
    return candidate


def accepted_value(
    final_value: Any,
    chosen_source: str,
    confidence: str,
    resolution_method: str,
    provenance: dict,
    competing_candidates: list[dict] | None = None,
    inherited: bool = False,
    manually_approved: bool = False,
    conflict_status: str = "none",
) -> dict:
    """Build an accepted-value envelope that preserves provenance."""
    return {
        "final_value": final_value,
        "chosen_source": chosen_source,
        "confidence": confidence,
        "resolution_method": resolution_method,
        "provenance": provenance,
        "inherited": inherited,
        "manually_approved": manually_approved,
        "competing_candidates": competing_candidates or [],
        "conflict_status": conflict_status,
    }


def validate_candidate_schema(candidate: dict) -> list[str]:
    missing = [field for field in CANDIDATE_VALUE_FIELDS if field not in candidate]
    errors = []
    if missing:
        errors.append(f"missing candidate keys: {', '.join(missing)}")
    if candidate.get("inheritance_used") and not candidate.get("inheritance_scope"):
        errors.append("inheritance_scope is required when inheritance_used is true")
    if candidate.get("field_confidence") is not None and not 0 <= float(candidate["field_confidence"]) <= 1:
        errors.append("field_confidence must be between 0 and 1")
    return errors


def validate_accepted_schema(value: dict) -> list[str]:
    missing = [field for field in ACCEPTED_VALUE_FIELDS if field not in value]
    errors = []
    if missing:
        errors.append(f"missing accepted-value keys: {', '.join(missing)}")
    if not value.get("provenance"):
        errors.append("accepted value requires provenance")
    return errors
