"""CarDekho shared-spec adapter placeholder.

Future exact model or variant parsing can implement this adapter. This batch
keeps it conservative and returns no values unless a later controlled source
probe supplies structured evidence.
"""

from __future__ import annotations

from scraping.enrichment.adapters.base import SourceAdapter
from scraping.enrichment.adapters.oem_spec_adapter import TARGET_FIELDS


class CarDekhoSpecAdapter(SourceAdapter):
    source_name = "CarDekho exact model or variant page"
    supported_fields = TARGET_FIELDS

    def find_record(self, record: dict) -> dict | None:
        return None

    def extract_candidates(self, record: dict, fields: list[str]) -> list[dict]:
        return []
