"""CarWale shared-spec adapter placeholder.

This adapter intentionally does not scrape or infer values. It exists so future
CarWale structured-state extraction can plug into the shared-spec batch without
changing the batch coordinator.
"""

from __future__ import annotations

from scraping.enrichment.adapters.base import SourceAdapter
from scraping.enrichment.adapters.oem_spec_adapter import TARGET_FIELDS


class CarWaleSpecAdapter(SourceAdapter):
    source_name = "CarWale structured state"
    supported_fields = TARGET_FIELDS

    def find_record(self, record: dict) -> dict | None:
        source_url = record.get("source_url")
        if source_url and "carwale.com" in source_url:
            return {"source_url": source_url}
        return None

    def extract_candidates(self, record: dict, fields: list[str]) -> list[dict]:
        # Current cleaned active tree no longer retains CarWale state files.
        # Missing values must therefore remain null rather than inferred.
        return []
