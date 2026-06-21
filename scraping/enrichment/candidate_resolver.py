"""Deterministic candidate resolution rules."""

from __future__ import annotations


RESOLUTION_ORDER = (
    "exact official variant source",
    "exact official brochure",
    "exact trusted portal match",
    "safe powertrain/model inheritance",
    "manual review",
    "unresolved conflict",
)


def resolution_rank(candidate: dict) -> int:
    method = candidate.get("resolution_method") or candidate.get("source_type") or ""
    for index, label in enumerate(RESOLUTION_ORDER):
        if label in method:
            return index
    if candidate.get("source_type") == "official_variant":
        return 0
    if candidate.get("source_type") == "official_brochure":
        return 1
    if candidate.get("exact_match_confidence", 0) >= 0.9 and candidate.get("source_type") == "trusted_portal":
        return 2
    if candidate.get("inheritance_used"):
        return 3
    return 4


def resolve_candidates(candidates: list[dict], conflicts: list[dict] | None = None) -> dict:
    if conflicts:
        return {"status": "unresolved_conflict", "candidate": None, "reason": "conflicts require manual review"}
    valid = [candidate for candidate in candidates if candidate.get("validation_status") in {"VALID", "UNVALIDATED"}]
    if not valid:
        return {"status": "manual_review", "candidate": None, "reason": "no valid candidates"}
    valid.sort(key=lambda item: (resolution_rank(item), -(item.get("field_confidence") or 0)))
    return {"status": "accepted", "candidate": valid[0], "reason": "highest deterministic source rank"}

