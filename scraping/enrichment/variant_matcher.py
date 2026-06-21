"""Exact-variant matching helpers for variant-level enrichment."""

from __future__ import annotations

import re
from typing import Any


MATCH_EXACT = "EXACT"
MATCH_HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
MATCH_AMBIGUOUS = "AMBIGUOUS"
MATCH_MISMATCH = "MISMATCH"


TRANSMISSION_ALIASES = {
    "manual": {"manual", "mt"},
    "amt": {"amt", "automatic amt", "automated manual"},
    "dct": {"dct", "automatic dct"},
    "cvt": {"cvt", "automatic cvt"},
    "tc": {"tc", "torque converter", "automatic tc", "at"},
    "automatic": {"automatic", "at"},
}

SPECIAL_EDITION_TOKENS = ("dual tone", "dark", "red dark", "knight", "n line", "sport", "performance")


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("+", " plus ")
    text = re.sub(r"\bo\b", " o ", text)
    text = re.sub(r"[\(\)\[\],./_-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def token_set(value: Any) -> set[str]:
    return set(normalize_text(value).split())


def transmission_family(value: Any) -> str:
    text = normalize_text(value)
    if re.search(r"\bamt\b|automated manual", text):
        return "amt"
    if re.search(r"\bdct\b", text):
        return "dct"
    if re.search(r"\bcvt\b", text):
        return "cvt"
    if re.search(r"\btc\b|torque converter", text):
        return "tc"
    if re.search(r"\bmanual\b|\bmt\b", text):
        return "manual"
    if re.search(r"\bautomatic\b|\bat\b", text):
        return "automatic"
    return text or "unknown"


def special_edition_tokens(value: Any) -> set[str]:
    text = normalize_text(value)
    return {token for token in SPECIAL_EDITION_TOKENS if token in text}


def variant_base_tokens(value: Any) -> set[str]:
    tokens = token_set(value)
    drop = {
        "petrol",
        "diesel",
        "cng",
        "ev",
        "electric",
        "manual",
        "automatic",
        "amt",
        "dct",
        "cvt",
        "tc",
        "speed",
        "turbo",
        "dual",
        "tone",
        "dark",
        "red",
        "knight",
        "edition",
        "1",
        "2l",
        "5l",
        "15l",
        "12l",
    }
    return {token for token in tokens if token not in drop and not token.isdigit()}


def match_variant(canonical_record: dict[str, Any], source_record: dict[str, Any]) -> dict[str, Any]:
    """Return an exactness label plus the components used to decide it."""
    components = {
        "make_match": normalize_text(canonical_record.get("make")) == normalize_text(source_record.get("make")),
        "model_match": normalize_text(canonical_record.get("model")) == normalize_text(source_record.get("model")),
        "fuel_match": normalize_text(canonical_record.get("fuel_type")) == normalize_text(source_record.get("fuel_type")),
        "transmission_match": transmission_family(canonical_record.get("transmission"))
        == transmission_family(source_record.get("transmission")),
        "special_edition_match": special_edition_tokens(canonical_record.get("variant"))
        == special_edition_tokens(source_record.get("variant")),
    }
    canonical_tokens = variant_base_tokens(canonical_record.get("variant"))
    source_tokens = variant_base_tokens(source_record.get("variant"))
    components["variant_tokens_match"] = canonical_tokens == source_tokens
    components["canonical_variant_tokens"] = sorted(canonical_tokens)
    components["source_variant_tokens"] = sorted(source_tokens)
    components["canonical_transmission_family"] = transmission_family(canonical_record.get("transmission"))
    components["source_transmission_family"] = transmission_family(source_record.get("transmission"))

    required = ("make_match", "model_match", "fuel_match", "transmission_match", "special_edition_match")
    if not all(components[key] for key in required):
        status = MATCH_MISMATCH
    elif components["variant_tokens_match"]:
        status = MATCH_EXACT
    elif canonical_tokens and source_tokens and (canonical_tokens <= source_tokens or source_tokens <= canonical_tokens):
        status = MATCH_HIGH_CONFIDENCE
    else:
        status = MATCH_AMBIGUOUS
    return {
        "status": status,
        "components": components,
    }
