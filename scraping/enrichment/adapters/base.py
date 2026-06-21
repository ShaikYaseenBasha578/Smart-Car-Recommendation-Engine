"""Base source adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SourceAdapter(ABC):
    source_name = "base"
    supported_fields: tuple[str, ...] = ()

    def supports_field(self, field_name: str) -> bool:
        return field_name in self.supported_fields

    @abstractmethod
    def find_record(self, record: dict) -> dict | None:
        """Return a source-specific record match or None."""

    @abstractmethod
    def extract_candidates(self, record: dict, fields: list[str]) -> list[dict]:
        """Return candidate values for requested fields."""

    def normalize_candidate(self, candidate: dict) -> dict:
        return candidate

    def source_metadata(self) -> dict:
        return {
            "source_name": self.source_name,
            "supported_fields": list(self.supported_fields),
        }

