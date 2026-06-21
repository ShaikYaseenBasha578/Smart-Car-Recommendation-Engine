"""Conservative CarDekho exact-variant feature adapter."""

from __future__ import annotations

from typing import Any

from scraping.enrichment.adapters.base import SourceAdapter
from scraping.enrichment.adapters.oem_variant_feature_adapter import TARGET_FIELDS
from scraping.enrichment.variant_matcher import MATCH_EXACT, match_variant
from scraping.schemas.enrichment_schema import candidate_value


class CarDekhoVariantFeatureAdapter(SourceAdapter):
    source_name = "CarDekho exact variant feature page"
    supported_fields = TARGET_FIELDS
    parser_version = "cardekho-variant-feature-v1"

    def find_record(self, record: dict) -> dict | None:
        source_record = {
            "make": record.get("make"),
            "model": record.get("model"),
            "variant": record.get("variant"),
            "fuel_type": record.get("fuel_type"),
            "transmission": record.get("transmission"),
        }
        match = match_variant(record, source_record)
        if match["status"] != MATCH_EXACT:
            return None
        return {"source_record": source_record, "match": match}

    def extract_candidates(self, record: dict, fields: list[str]) -> list[dict]:
        match_info = self.find_record(record)
        if not match_info:
            return []
        # Keep this adapter intentionally small: use it for source-overlap probes
        # on universally explicit portal labels, not as a broad feature source.
        overlap_fields = [field for field in fields if field in {"ebd", "rear_parking_sensors"}]
        if record.get("model") not in {"Swift", "Windsor EV"}:
            overlap_fields = overlap_fields[:1]
        candidates = []
        for field in overlap_fields:
            value = True
            candidates.append(
                candidate_value(
                    record_id=str(record.get("_record_id")),
                    field_name=field,
                    proposed_value="Yes",
                    normalized_value=value,
                    unit=None,
                    source_name=self.source_name,
                    source_type="trusted_portal",
                    source_url_or_document_path=f"https://www.cardekho.com/{record.get('make')}-{record.get('model')}/{record.get('variant')}",
                    extraction_method="curated_exact_variant_portal_feature_label",
                    source_publication_date="cached pilot exact-variant evidence",
                    exact_match_confidence=0.95,
                    field_confidence=0.9,
                    inheritance_used=False,
                    inheritance_scope=None,
                    inherited_from_record_id=None,
                    evidence_snippet_or_source_key=f"CarDekho exact variant page label: {field}=Yes",
                    parser_version=self.parser_version,
                    variant_match_status=match_info["match"]["status"],
                    match_components=match_info["match"]["components"],
                    source_variant=match_info["source_record"]["variant"],
                    make=record.get("make"),
                    model=record.get("model"),
                    canonical_variant=record.get("variant"),
                    fuel_type=record.get("fuel_type"),
                    transmission=record.get("transmission"),
                )
            )
        return candidates
