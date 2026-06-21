"""Source registry for enrichment adapters."""

from __future__ import annotations


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, dict] = {}

    def register(self, source: str, adapter: object | None, supported_fields: list[str], field_scope: str, priority: int, confidence_ceiling: float) -> None:
        self._sources[source] = {
            "adapter": adapter,
            "supported_fields": supported_fields,
            "field_scope": field_scope,
            "priority": priority,
            "confidence_ceiling": confidence_ceiling,
        }

    def sources_for_field(self, field_name: str) -> list[dict]:
        matches = [
            {"source": source, **metadata}
            for source, metadata in self._sources.items()
            if field_name in metadata.get("supported_fields", [])
        ]
        return sorted(matches, key=lambda item: item["priority"])

    def as_dict(self) -> dict:
        return {
            source: {key: value for key, value in metadata.items() if key != "adapter"}
            for source, metadata in self._sources.items()
        }

