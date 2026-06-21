"""Helpers for sidecar null metadata."""

from __future__ import annotations

from scraping.schemas.null_reasons import field_null_reason, null_metadata


def build_record_null_metadata(record: dict, fields: list[str], policy: dict) -> dict:
    metadata = {}
    for field in fields:
        reason = field_null_reason(field, record, policy)
        if reason:
            metadata.update(null_metadata(field, reason))
    return metadata

