"""Candidate conflict detection."""

from __future__ import annotations

from typing import Any


def numeric_conflict(left: Any, right: Any, tolerance: float = 0.02) -> bool:
    try:
        a = float(left)
        b = float(right)
    except (TypeError, ValueError):
        return False
    if a == b:
        return False
    allowed_delta = max(abs(a), abs(b), 1) * tolerance
    return abs(a - b) > allowed_delta


def detect_conflicts(candidates: list[dict], field_name: str) -> list[dict]:
    conflicts = []
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            reason = None
            if left.get("unit") and right.get("unit") and left.get("unit") != right.get("unit"):
                reason = "unit mismatch"
            elif isinstance(left.get("normalized_value"), bool) or isinstance(right.get("normalized_value"), bool):
                if left.get("normalized_value") is not right.get("normalized_value"):
                    reason = "boolean disagreement"
            elif numeric_conflict(left.get("normalized_value"), right.get("normalized_value")):
                reason = "numeric values differ beyond tolerance"
            elif left.get("inheritance_scope") == "MODEL_LEVEL" and right.get("inheritance_scope") == "VARIANT_LEVEL":
                reason = "model-level vs variant-level contradiction"
            if reason:
                conflicts.append({"field_name": field_name, "left": left, "right": right, "reason": reason})
    return conflicts

