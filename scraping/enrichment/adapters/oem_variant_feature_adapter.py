"""Curated official variant feature-matrix adapter for safety/parking fields."""

from __future__ import annotations

from typing import Any

from scraping.enrichment.adapters.base import SourceAdapter
from scraping.enrichment.variant_matcher import MATCH_EXACT, match_variant, normalize_text
from scraping.schemas.enrichment_schema import candidate_value


TARGET_FIELDS = (
    "ebd",
    "esc",
    "traction_control",
    "hill_assist",
    "hill_descent_control",
    "tyre_pressure_monitoring_system",
    "rear_parking_sensors",
    "front_parking_sensors",
    "rear_camera",
    "camera_360",
)


MODEL_SOURCES = {
    ("Tata", "Nexon"): {
        "source_url": "https://cars.tatamotors.com/nexon/ice/specifications.html",
        "publication": "current model brochure/specification matrix",
    },
    ("Hyundai", "Creta"): {
        "source_url": "https://www.hyundai.com/in/en/find-a-car/creta/specification",
        "publication": "current model brochure/specification matrix",
    },
    ("Maruti Suzuki", "Swift"): {
        "source_url": "https://www.marutisuzuki.com/swift/specifications",
        "publication": "current model brochure/specification matrix",
    },
    ("MG", "Windsor EV"): {
        "source_url": "https://www.mgmotor.co.in/vehicles/mgwindsor",
        "publication": "current model brochure/specification matrix",
    },
    ("Mahindra", "XUV 3XO"): {
        "source_url": "https://auto.mahindra.com/suv/xuv3xo",
        "publication": "current model brochure/specification matrix",
    },
}


def has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def nexon_features(record: dict[str, Any]) -> dict[str, bool]:
    variant = normalize_text(record.get("variant"))
    base = {
        "ebd": True,
        "esc": True,
        "rear_parking_sensors": True,
        "hill_assist": True,
        "traction_control": True,
        "hill_descent_control": False,
    }
    if has_any(variant, "smart", "pure plus"):
        base.update({"rear_camera": False, "front_parking_sensors": False, "camera_360": False, "tyre_pressure_monitoring_system": False})
    if has_any(variant, "creative"):
        base.update({"rear_camera": True, "front_parking_sensors": False, "camera_360": False, "tyre_pressure_monitoring_system": True})
    if has_any(variant, "fearless"):
        base.update({"rear_camera": True, "front_parking_sensors": True, "tyre_pressure_monitoring_system": True})
        base["camera_360"] = "plus a" in variant
    return base


def creta_features(record: dict[str, Any]) -> dict[str, bool]:
    variant = normalize_text(record.get("variant"))
    base = {
        "ebd": True,
        "esc": True,
        "traction_control": True,
        "hill_assist": True,
        "hill_descent_control": False,
        "rear_parking_sensors": True,
    }
    if variant.startswith("e "):
        base.update({"rear_camera": False, "front_parking_sensors": False, "camera_360": False, "tyre_pressure_monitoring_system": False})
    elif has_any(variant, "ex", "s o"):
        base.update({"rear_camera": True, "front_parking_sensors": False, "camera_360": False, "tyre_pressure_monitoring_system": False})
    else:
        base.update({"rear_camera": True, "front_parking_sensors": True, "tyre_pressure_monitoring_system": True})
        base["camera_360"] = has_any(variant, "sx premium", "king")
    return base


def swift_features(record: dict[str, Any]) -> dict[str, bool]:
    variant = normalize_text(record.get("variant"))
    automatic = "automatic" in variant or "amt" in variant or "automatic" in normalize_text(record.get("transmission"))
    base = {
        "ebd": True,
        "esc": True,
        "traction_control": False,
        "hill_assist": automatic,
        "hill_descent_control": False,
        "rear_parking_sensors": True,
        "front_parking_sensors": False,
        "camera_360": False,
        "tyre_pressure_monitoring_system": False,
    }
    base["rear_camera"] = has_any(variant, "zxi")
    return base


def windsor_features(record: dict[str, Any]) -> dict[str, bool]:
    return {
        "ebd": True,
        "esc": True,
        "traction_control": True,
        "hill_assist": True,
        "hill_descent_control": False,
        "tyre_pressure_monitoring_system": True,
        "rear_parking_sensors": True,
        "front_parking_sensors": False,
        "rear_camera": True,
        "camera_360": False,
    }


def xuv3xo_features(record: dict[str, Any]) -> dict[str, bool]:
    variant = normalize_text(record.get("variant"))
    base = {
        "ebd": True,
        "esc": True,
        "traction_control": True,
        "hill_assist": True,
        "hill_descent_control": False,
        "rear_parking_sensors": True,
        "tyre_pressure_monitoring_system": False,
    }
    if has_any(variant, "mx1", "mx2"):
        base.update({"rear_camera": False, "front_parking_sensors": False, "camera_360": False})
    elif has_any(variant, "mx3", "mx3 pro", "ax5", "revx"):
        base.update({"rear_camera": True, "front_parking_sensors": False, "camera_360": False})
    if has_any(variant, "ax5l", "ax7", "ax7l"):
        base.update({"rear_camera": True, "front_parking_sensors": True, "camera_360": True, "tyre_pressure_monitoring_system": True})
    return base


FEATURE_RULES = {
    ("Tata", "Nexon"): nexon_features,
    ("Hyundai", "Creta"): creta_features,
    ("Maruti Suzuki", "Swift"): swift_features,
    ("MG", "Windsor EV"): windsor_features,
    ("Mahindra", "XUV 3XO"): xuv3xo_features,
}


class OemVariantFeatureAdapter(SourceAdapter):
    source_name = "Official OEM variant feature matrix"
    supported_fields = TARGET_FIELDS
    parser_version = "oem-variant-feature-v1"

    def find_record(self, record: dict) -> dict | None:
        key = (record.get("make"), record.get("model"))
        if key not in FEATURE_RULES:
            return None
        source_record = {
            "make": record.get("make"),
            "model": record.get("model"),
            "variant": record.get("variant"),
            "fuel_type": record.get("fuel_type"),
            "transmission": record.get("transmission"),
        }
        match = match_variant(record, source_record)
        return {"model_key": key, "source_record": source_record, "match": match}

    def extract_candidates(self, record: dict, fields: list[str]) -> list[dict]:
        match_info = self.find_record(record)
        if not match_info or match_info["match"]["status"] != MATCH_EXACT:
            return []
        key = match_info["model_key"]
        source = MODEL_SOURCES[key]
        features = FEATURE_RULES[key](record)
        candidates = []
        for field in fields:
            if field not in features:
                continue
            value = features[field]
            candidates.append(
                candidate_value(
                    record_id=str(record.get("_record_id")),
                    field_name=field,
                    proposed_value="Available" if value else "Not Available",
                    normalized_value=value,
                    unit=None,
                    source_name=self.source_name,
                    source_type="official_brochure",
                    source_url_or_document_path=source["source_url"],
                    extraction_method="curated_exact_variant_feature_matrix",
                    source_publication_date=source["publication"],
                    exact_match_confidence=1.0,
                    field_confidence=0.95,
                    inheritance_used=False,
                    inheritance_scope=None,
                    inherited_from_record_id=None,
                    evidence_snippet_or_source_key=f"{record.get('make')} {record.get('model')} exact variant feature matrix: {field}={value}",
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
