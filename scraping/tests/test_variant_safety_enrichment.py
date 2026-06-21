"""Tests for exact-variant safety enrichment."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from scraping.enrichment.adapters.oem_variant_feature_adapter import OemVariantFeatureAdapter
from scraping.enrichment.conflict_detector import detect_conflicts
from scraping.enrichment.variant_matcher import MATCH_AMBIGUOUS, MATCH_EXACT, MATCH_MISMATCH, match_variant


ROOT = Path(".")
INPUT = ROOT / "datasets/interim/shared_spec_enrichment/enriched_records.json"
OUTPUT = ROOT / "datasets/interim/variant_safety_enrichment/enriched_records.json"


class VariantSafetyEnrichmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.input_records = json.loads(INPUT.read_text(encoding="utf-8"))
        cls.output_records = json.loads(OUTPUT.read_text(encoding="utf-8"))
        cls.candidates = json.loads((ROOT / "datasets/interim/variant_safety_enrichment/candidates.json").read_text(encoding="utf-8"))
        cls.dispositions = json.loads((ROOT / "scraping/outputs/variant_safety_candidate_disposition.json").read_text(encoding="utf-8"))
        cls.manual_review = json.loads((ROOT / "scraping/outputs/variant_safety_manual_review.json").read_text(encoding="utf-8"))

    def test_exact_variant_match(self) -> None:
        record = {
            "make": "Tata",
            "model": "Nexon",
            "variant": "Creative Petrol 1.2L Turbo Automatic (AMT)",
            "fuel_type": "Petrol",
            "transmission": "Automatic (AMT)",
        }
        self.assertEqual(match_variant(record, dict(record))["status"], MATCH_EXACT)

    def test_ambiguous_trim_match_withheld(self) -> None:
        canonical = {"make": "Hyundai", "model": "Creta", "variant": "EX Petrol Manual", "fuel_type": "Petrol", "transmission": "Manual"}
        source = {"make": "Hyundai", "model": "Creta", "variant": "SX Petrol Manual", "fuel_type": "Petrol", "transmission": "Manual"}
        self.assertEqual(match_variant(canonical, source)["status"], MATCH_AMBIGUOUS)

    def test_fuel_and_transmission_mismatch_rejected(self) -> None:
        canonical = {"make": "Tata", "model": "Nexon", "variant": "Smart", "fuel_type": "Petrol", "transmission": "Manual"}
        fuel_source = {**canonical, "fuel_type": "Diesel"}
        trans_source = {**canonical, "transmission": "Automatic (AMT)"}
        self.assertEqual(match_variant(canonical, fuel_source)["status"], MATCH_MISMATCH)
        self.assertEqual(match_variant(canonical, trans_source)["status"], MATCH_MISMATCH)

    def test_special_edition_mismatch_rejected(self) -> None:
        canonical = {
            "make": "Tata",
            "model": "Nexon",
            "variant": "Fearless Plus Petrol Dark Edition",
            "fuel_type": "Petrol",
            "transmission": "Manual",
        }
        source = {**canonical, "variant": "Fearless Plus Petrol"}
        self.assertEqual(match_variant(canonical, source)["status"], MATCH_MISMATCH)

    def test_base_and_top_trims_remain_distinct(self) -> None:
        by_variant = {wrapper["canonical_record"]["variant"]: wrapper["canonical_record"] for wrapper in self.output_records if wrapper["canonical_record"]["model"] == "Nexon"}
        base = by_variant["Smart Petrol 1.2L Turbo 5 Speed Manual"]
        top = by_variant["Fearless Plus A (PS) Petrol 1.2L Turbo Automatic (DCT)"]
        base_values = tuple(base[field] for field in ("rear_camera", "front_parking_sensors", "camera_360"))
        top_values = tuple(top[field] for field in ("rear_camera", "front_parking_sensors", "camera_360"))
        self.assertNotEqual(base_values, top_values)

    def test_explicit_not_available_becomes_false(self) -> None:
        record = {
            "_record_id": "swift-lxi",
            "make": "Maruti Suzuki",
            "model": "Swift",
            "variant": "LXi Petrol Manual",
            "fuel_type": "Petrol",
            "transmission": "Manual",
        }
        candidates = OemVariantFeatureAdapter().extract_candidates(record, ["rear_camera"])
        self.assertEqual(candidates[0]["proposed_value"], "Not Available")
        self.assertIs(candidates[0]["normalized_value"], False)

    def test_missing_feature_text_remains_null(self) -> None:
        unknown = {"_record_id": "unknown", "make": "Example", "model": "Unknown", "variant": "Base", "fuel_type": "Petrol", "transmission": "Manual"}
        self.assertEqual(OemVariantFeatureAdapter().extract_candidates(unknown, ["rear_camera"]), [])

    def test_no_model_or_powertrain_inheritance(self) -> None:
        self.assertTrue(all(not candidate.get("inheritance_used") for candidate in self.candidates))
        self.assertTrue(all(candidate.get("inheritance_scope") is None for candidate in self.candidates))

    def test_direct_true_false_conflict_remains_unresolved(self) -> None:
        conflicts = detect_conflicts(
            [{"normalized_value": True, "source_name": "Official"}, {"normalized_value": False, "source_name": "Portal"}],
            "rear_camera",
        )
        self.assertEqual(conflicts[0]["reason"], "boolean disagreement")

    def test_official_source_supersedes_lower_priority_agreeing_source(self) -> None:
        totals = Counter(row["terminal_status"] for row in self.dispositions)
        self.assertGreater(totals["SUPERSEDED_BY_HIGHER_PRIORITY_SOURCE"], 0)
        superseded = next(row for row in self.dispositions if row["terminal_status"] == "SUPERSEDED_BY_HIGHER_PRIORITY_SOURCE")
        self.assertTrue(superseded["winning_candidate_id"])

    def test_default_page_mismatch_detection(self) -> None:
        canonical = {"make": "MG", "model": "Windsor EV", "variant": "Excite 38.0 kWh", "fuel_type": "Electric", "transmission": "Automatic"}
        default_page = {**canonical, "variant": "Essence 38.0 kWh"}
        self.assertEqual(match_variant(canonical, default_page)["status"], MATCH_AMBIGUOUS)

    def test_every_candidate_receives_one_disposition(self) -> None:
        self.assertEqual(len(self.candidates), len(self.dispositions))
        self.assertTrue(all(row.get("terminal_status") for row in self.dispositions))

    def test_unresolved_no_candidate_cells_excluded_from_candidate_totals(self) -> None:
        self.assertEqual(len(self.manual_review), 0)
        self.assertEqual(len(self.candidates), 1390)

    def test_shared_spec_fields_remain_unchanged(self) -> None:
        shared_fields = (
            "boot_space_litres",
            "ground_clearance_mm",
            "turning_radius_metres",
            "fuel_tank_capacity_litres",
            "drivetrain",
            "cylinders",
            "turbocharged",
            "gearbox_speeds",
            "length_mm",
            "width_mm",
            "height_mm",
            "wheelbase_mm",
        )
        before = {str(wrapper.get("version_id")): wrapper["canonical_record"] for wrapper in self.input_records}
        after = {str(wrapper.get("version_id")): wrapper["canonical_record"] for wrapper in self.output_records}
        for record_id, before_record in before.items():
            for field in shared_fields:
                self.assertEqual(before_record.get(field), after[record_id].get(field), (record_id, field))


if __name__ == "__main__":
    unittest.main()
