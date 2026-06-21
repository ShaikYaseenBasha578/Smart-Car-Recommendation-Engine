"""Policy-only inheritance checks."""

from __future__ import annotations


def check_inheritance_allowed(field_name: str, source_record: dict, target_record: dict, policy: dict) -> dict:
    field_policy = policy.get(field_name, {})
    if not field_policy.get("inheritance", {}).get("allowed"):
        return {"allowed": False, "blocked": True, "reason": "inheritance not allowed by policy"}

    source_scope = field_policy.get("expected_scope")
    valid_scopes = field_policy.get("inheritance", {}).get("valid_source_scopes") or []
    if source_scope not in valid_scopes:
        return {"allowed": False, "blocked": True, "reason": f"scope {source_scope} is not a valid inheritance source"}

    if source_record.get("make") != target_record.get("make") or source_record.get("model") != target_record.get("model"):
        return {"allowed": False, "blocked": True, "reason": "make/model mismatch"}

    if source_scope == "POWERTRAIN_LEVEL":
        for field in ("fuel_type", "engine_cc", "transmission"):
            if source_record.get(field) != target_record.get(field):
                return {"allowed": False, "blocked": True, "reason": f"powertrain mismatch on {field}"}

    if source_scope == "TRIM_FAMILY_LEVEL" and source_record.get("variant") != target_record.get("variant"):
        return {"allowed": False, "blocked": True, "reason": "trim-level inheritance requires explicit trim-family evidence"}

    return {
        "allowed": True,
        "blocked": False,
        "reason": "policy conditions satisfied",
        "source_scope": source_scope,
        "target_scope": field_policy.get("expected_scope"),
        "confidence_adjustment": -0.05 if source_scope != "VARIANT_LEVEL" else 0,
    }

