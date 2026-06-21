"""Tests for the canonical missing-field enrichment framework."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scraping.enrichment.conflict_detector import detect_conflicts
from scraping.enrichment.inheritance import check_inheritance_allowed
from scraping.enrichment.missing_field_detector import missing_fields_for_record, prioritized_enrichment_queue
from scraping.enrichment.validators import validate_candidate
from scraping.schemas.enrichment_schema import (
    accepted_value,
    candidate_value,
    validate_accepted_schema,
    validate_candidate_schema,
)
from scraping.schemas.null_reasons import field_null_reason
from scraping.sources.recommendation_completeness import weighted_completeness_for_record


POLICY = json.loads(Path("scraping/config/field_enrichment_policy.json").read_text(encoding="utf-8"))


def wrapper(record: dict) -> dict:
    return {"version_id": "test", "canonical_record": record}


class EnrichmentFrameworkTest(unittest.TestCase):
    def test_ev_and_cng_applicability(self) -> None:
        ev = {"fuel_type": "Electric"}
        cng = {"fuel_type": "CNG"}
        petrol = {"fuel_type": "Petrol"}
        self.assertEqual(field_null_reason("engine_cc", ev, POLICY), "NOT_APPLICABLE")
        self.assertEqual(field_null_reason("mileage_arai_km_per_kg", petrol, POLICY), "NOT_APPLICABLE")
        self.assertEqual(field_null_reason("mileage_arai_kmpl", cng, POLICY), "NOT_APPLICABLE")
        self.assertEqual(field_null_reason("mileage_arai_km_per_kg", cng, POLICY), "NOT_YET_ENRICHED")

    def test_missing_boolean_is_not_false(self) -> None:
        record = {
            "make": "Tata",
            "model": "Nexon",
            "variant": "Smart",
            "fuel_type": "Petrol",
            "transmission": "Manual",
            "rear_camera": None,
        }
        missing = missing_fields_for_record(wrapper(record), POLICY)
        rear_camera = [item for item in missing if item["missing_field"] == "rear_camera"]
        self.assertEqual(len(rear_camera), 1)
        self.assertTrue(rear_camera[0]["manual_review_likelihood"] in {"medium", "high"})

    def test_inheritance_blocks_powertrain_mismatch(self) -> None:
        source = {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Manual"}
        target = {"make": "Tata", "model": "Nexon", "fuel_type": "Diesel", "engine_cc": 1497, "transmission": "Manual"}
        result = check_inheritance_allowed("power_bhp", source, target, POLICY)
        self.assertFalse(result["allowed"])
        self.assertIn("mismatch", result["reason"])

    def test_inheritance_allows_model_level_body_type(self) -> None:
        source = {"make": "Hyundai", "model": "Creta", "fuel_type": "Petrol"}
        target = {"make": "Hyundai", "model": "Creta", "fuel_type": "Diesel"}
        result = check_inheritance_allowed("body_type", source, target, POLICY)
        self.assertTrue(result["allowed"])

    def test_conflict_detection(self) -> None:
        conflicts = detect_conflicts(
            [
                {"normalized_value": 17.4, "unit": "km/l", "source_type": "trusted_portal"},
                {"normalized_value": 21.8, "unit": "km/l", "source_type": "official_brochure"},
            ],
            "mileage_arai_kmpl",
        )
        self.assertEqual(conflicts[0]["reason"], "numeric values differ beyond tolerance")
        boolean_conflicts = detect_conflicts(
            [{"normalized_value": True}, {"normalized_value": False}],
            "abs",
        )
        self.assertEqual(boolean_conflicts[0]["reason"], "boolean disagreement")

    def test_candidate_and_accepted_value_schema(self) -> None:
        candidate = candidate_value(
            record_id="1",
            field_name="airbags",
            normalized_value=6,
            source_name="CarDekho",
            source_type="trusted_portal",
            field_confidence=0.95,
        )
        self.assertEqual(validate_candidate_schema(candidate), [])
        accepted = accepted_value(
            final_value=6,
            chosen_source="CarDekho",
            confidence="high",
            resolution_method="exact trusted portal match",
            provenance={"source": "cached html"},
        )
        self.assertEqual(validate_accepted_schema(accepted), [])

    def test_queue_priority_prefers_core_fields(self) -> None:
        record = {
            "make": "Tata",
            "model": "Nexon",
            "variant": "Smart",
            "full_name": "Tata Nexon Smart",
            "fuel_type": "Petrol",
            "transmission": "Manual",
            "source": "CarWale",
            "source_url": "https://example.test",
            "scraped_at": "2026-01-01T00:00:00+00:00",
        }
        queue = prioritized_enrichment_queue([wrapper(record)], POLICY)
        self.assertGreaterEqual(queue[0]["field_priority"], queue[-1]["field_priority"])
        self.assertIn(queue[0]["category"], {"CORE_REQUIRED", "HIGH_VALUE"})

    def test_weighted_completeness_ignores_not_applicable_ev_ice_fields(self) -> None:
        ev = {
            "make": "MG",
            "model": "Windsor EV",
            "variant": "Excite",
            "full_name": "MG Windsor EV Excite",
            "body_type": "MUV",
            "fuel_type": "Electric",
            "transmission": "Automatic",
            "price_ex_showroom": 1400000,
            "claimed_ev_range_km": 331,
            "airbags": 6,
            "abs": True,
            "source": "CarWale",
            "source_url": "https://example.test",
            "scraped_at": "2026-01-01T00:00:00+00:00",
        }
        score = weighted_completeness_for_record(ev, POLICY)
        self.assertNotIn("mileage_arai_kmpl", score["missing_weight_by_field"])
        self.assertNotIn("engine_cc", score["missing_weight_by_field"])

    def test_numeric_validation_rejects_wrong_mileage_slot(self) -> None:
        cng = {"fuel_type": "CNG"}
        self.assertIn("CNG mileage", " ".join(validate_candidate(cng, "mileage_arai_kmpl", 24.0)))
        ev = {"fuel_type": "Electric"}
        self.assertIn("should be null for EV", " ".join(validate_candidate(ev, "engine_cc", 1199)))


if __name__ == "__main__":
    unittest.main()
