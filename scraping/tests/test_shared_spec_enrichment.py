"""Tests for the shared-spec enrichment batch."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scraping.enrichment.adapters.oem_spec_adapter import OemSpecAdapter
from scraping.enrichment.conflict_detector import detect_conflicts
from scraping.enrichment.inheritance import check_inheritance_allowed
from scraping.enrichment.validators import validate_candidate


POLICY = json.loads(Path("scraping/config/field_enrichment_policy.json").read_text(encoding="utf-8"))


class SharedSpecEnrichmentTest(unittest.TestCase):
    def test_model_dimensions_inherited_within_same_model(self) -> None:
        source = {"make": "Hyundai", "model": "Creta", "fuel_type": "Petrol"}
        target = {"make": "Hyundai", "model": "Creta", "fuel_type": "Diesel"}
        result = check_inheritance_allowed("length_mm", source, target, POLICY)
        self.assertTrue(result["allowed"])

    def test_dimensions_blocked_across_different_models(self) -> None:
        source = {"make": "Hyundai", "model": "Creta", "fuel_type": "Petrol"}
        target = {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol"}
        result = check_inheritance_allowed("length_mm", source, target, POLICY)
        self.assertFalse(result["allowed"])
        self.assertIn("make/model mismatch", result["reason"])

    def test_boot_space_not_copied_to_cng_without_explicit_evidence(self) -> None:
        record = {
            "_record_id": "nexon-cng",
            "make": "Tata",
            "model": "Nexon",
            "variant": "Smart CNG",
            "fuel_type": "CNG",
            "engine_cc": 1199,
            "transmission": "Manual",
        }
        fields = ["boot_space_litres", "fuel_tank_capacity_litres", "drivetrain", "cylinders"]
        candidates = OemSpecAdapter().extract_candidates(record, fields)
        candidate_fields = {candidate["field_name"] for candidate in candidates}
        self.assertNotIn("boot_space_litres", candidate_fields)
        self.assertNotIn("fuel_tank_capacity_litres", candidate_fields)
        self.assertIn("drivetrain", candidate_fields)
        self.assertIn("cylinders", candidate_fields)

    def test_ev_rejects_fuel_tank_cylinders_and_turbo(self) -> None:
        ev = {"fuel_type": "Electric"}
        self.assertTrue(validate_candidate(ev, "fuel_tank_capacity_litres", 40))
        self.assertTrue(validate_candidate(ev, "cylinders", 4))
        self.assertTrue(validate_candidate(ev, "turbocharged", False))

    def test_gearbox_speeds_not_inherited_across_manual_and_automatic(self) -> None:
        source = {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Manual"}
        target = {
            "make": "Tata",
            "model": "Nexon",
            "fuel_type": "Petrol",
            "engine_cc": 1199,
            "transmission": "Automatic (DCT)",
        }
        result = check_inheritance_allowed("gearbox_speeds", source, target, POLICY)
        self.assertFalse(result["allowed"])
        self.assertIn("transmission", result["reason"])

    def test_kerb_weight_conflicts_are_detected(self) -> None:
        conflicts = detect_conflicts(
            [
                {"normalized_value": 1200, "unit": "kg", "inheritance_scope": "POWERTRAIN_LEVEL"},
                {"normalized_value": 1380, "unit": "kg", "inheritance_scope": "POWERTRAIN_LEVEL"},
            ],
            "kerb_weight_kg",
        )
        self.assertEqual(conflicts[0]["reason"], "numeric values differ beyond tolerance")

    def test_inherited_values_keep_provenance(self) -> None:
        data = json.loads(Path("datasets/interim/shared_spec_enrichment/enriched_records.json").read_text(encoding="utf-8"))
        enriched = [
            wrapper
            for wrapper in data
            if wrapper.get("shared_spec_enrichment_provenance", {}).get("length_mm")
        ]
        self.assertTrue(enriched)
        provenance = enriched[0]["shared_spec_enrichment_provenance"]["length_mm"]
        self.assertTrue(provenance["inherited"])
        self.assertEqual(provenance["inheritance_scope"], "MODEL_LEVEL")
        self.assertTrue(provenance["source_url_or_document_path"])

    def test_missing_source_values_remain_null(self) -> None:
        data = json.loads(Path("datasets/interim/shared_spec_enrichment/enriched_records.json").read_text(encoding="utf-8"))
        self.assertTrue(all(wrapper["canonical_record"].get("kerb_weight_kg") is None for wrapper in data))

    def test_no_unrelated_boolean_false_inference(self) -> None:
        data = json.loads(Path("datasets/interim/shared_spec_enrichment/enriched_records.json").read_text(encoding="utf-8"))
        self.assertTrue(all(wrapper["canonical_record"].get("rear_camera") is None for wrapper in data))


if __name__ == "__main__":
    unittest.main()
