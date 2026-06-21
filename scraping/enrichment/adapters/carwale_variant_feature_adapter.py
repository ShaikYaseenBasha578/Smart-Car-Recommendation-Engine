"""CarWale exact-variant feature adapter placeholder for the safety batch."""

from __future__ import annotations

from scraping.enrichment.adapters.base import SourceAdapter
from scraping.enrichment.adapters.oem_variant_feature_adapter import TARGET_FIELDS


class CarWaleVariantFeatureAdapter(SourceAdapter):
    source_name = "CarWale exact variant page"
    supported_fields = TARGET_FIELDS

    def find_record(self, record: dict) -> dict | None:
        return None

    def extract_candidates(self, record: dict, fields: list[str]) -> list[dict]:
        # No active exact-variant CarWale feature evidence is retained after cleanup.
        return []
