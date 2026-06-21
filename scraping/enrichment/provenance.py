"""Provenance helpers for enrichment output."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def provenance_entry(
    field_name: str,
    source_name: str,
    source_url_or_document_path: str | None,
    evidence: str | None,
    confidence: str,
    inherited: bool = False,
    inheritance_scope: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "source_name": source_name,
        "source_url_or_document_path": source_url_or_document_path,
        "evidence": evidence,
        "confidence": confidence,
        "inherited": inherited,
        "inheritance_scope": inheritance_scope,
        "notes": notes,
        "recorded_at": utc_now_iso(),
    }

