"""Regression tests for shared-spec batch accounting hardening."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from scraping.enrichment.conflict_detector import detect_conflicts
from scraping.enrichment.inheritance import check_inheritance_allowed


ROOT = Path(".")
POLICY = json.loads((ROOT / "scraping/config/field_enrichment_policy.json").read_text(encoding="utf-8"))


class SharedSpecAccountingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dispositions = json.loads((ROOT / "scraping/outputs/shared_spec_candidate_disposition.json").read_text(encoding="utf-8"))
        cls.manual_review = json.loads((ROOT / "scraping/outputs/shared_spec_manual_review.json").read_text(encoding="utf-8"))
        cls.inheritance_audit = json.loads((ROOT / "scraping/outputs/shared_spec_inheritance_audit.json").read_text(encoding="utf-8"))
        cls.enriched = json.loads((ROOT / "datasets/interim/shared_spec_enrichment/enriched_records.json").read_text(encoding="utf-8"))

    def test_every_candidate_has_one_terminal_status(self) -> None:
        valid_statuses = {
            "ACCEPTED",
            "REJECTED_VALIDATION",
            "REJECTED_LOW_CONFIDENCE",
            "REJECTED_SCOPE_MISMATCH",
            "REJECTED_INHERITANCE_POLICY",
            "DUPLICATE_CANDIDATE",
            "SUPERSEDED_BY_HIGHER_PRIORITY_SOURCE",
            "EXISTING_VALUE_PRESERVED",
            "CONFLICT_UNRESOLVED",
            "NOT_APPLICABLE",
        }
        self.assertTrue(self.dispositions)
        for row in self.dispositions:
            self.assertIn(row["terminal_status"], valid_statuses)
            self.assertEqual(len([row["terminal_status"]]), 1)

    def test_reconciled_counts_match_batch_outputs(self) -> None:
        totals = Counter(row["terminal_status"] for row in self.dispositions)
        self.assertEqual(len(self.dispositions), 1422)
        self.assertEqual(totals["ACCEPTED"], 1134)
        self.assertEqual(len(self.manual_review), 201)
        self.assertEqual(sum(totals.values()), 1422)

    def test_duplicate_candidates_do_not_change_final_values(self) -> None:
        duplicates = [row for row in self.dispositions if row["terminal_status"] == "DUPLICATE_CANDIDATE"]
        self.assertEqual(len(duplicates), 1)
        duplicate = duplicates[0]
        accepted = [
            row
            for row in self.dispositions
            if row["candidate_id"] == duplicate["winning_candidate_id"] and row["terminal_status"] == "ACCEPTED"
        ]
        self.assertEqual(len(accepted), 1)
        record = next(wrapper for wrapper in self.enriched if str(wrapper.get("version_id")) == duplicate["record_id"])
        self.assertEqual(record["canonical_record"][duplicate["field"]], accepted[0]["normalized_value"])

    def test_preserved_existing_candidates_do_not_change_final_values(self) -> None:
        preserved = [row for row in self.dispositions if row["terminal_status"] == "EXISTING_VALUE_PRESERVED"]
        self.assertTrue(preserved)
        sample = preserved[0]
        record = next(wrapper for wrapper in self.enriched if str(wrapper.get("version_id")) == sample["record_id"])
        self.assertEqual(record["canonical_record"][sample["field"]], sample["existing_preserved_value"])

    def test_competing_candidates_reach_conflict_detection(self) -> None:
        conflicts = detect_conflicts(
            [
                {"normalized_value": 364, "unit": "litres", "source_name": "Official OEM specifications"},
                {"normalized_value": 382, "unit": "litres", "source_name": "Portal page"},
            ],
            "boot_space_litres",
        )
        self.assertEqual(conflicts[0]["reason"], "numeric values differ beyond tolerance")

    def test_incompatible_inheritance_attempts_are_visibly_blocked(self) -> None:
        cases = self.inheritance_audit["policy_block_test_cases"]
        self.assertTrue(cases)
        self.assertTrue(all(case["blocked"] for case in cases))

    def test_all_unresolved_cells_have_valid_null_reason(self) -> None:
        valid_reasons = {
            "SOURCE_UNAVAILABLE",
            "LOW_CONFIDENCE_MATCH",
            "UNSAFE_TO_INHERIT",
            "FIELD_NOT_PUBLISHED",
            "NOT_APPLICABLE",
        }
        self.assertEqual(len(self.manual_review), 201)
        for row in self.manual_review:
            self.assertIn(row.get("null_reason"), valid_reasons)

    def test_policy_blocks_manual_to_automatic_gearbox(self) -> None:
        source = {"make": "Tata", "model": "Nexon", "fuel_type": "Petrol", "engine_cc": 1199, "transmission": "Manual"}
        target = {
            "make": "Tata",
            "model": "Nexon",
            "fuel_type": "Petrol",
            "engine_cc": 1199,
            "transmission": "Automatic (DCT)",
        }
        result = check_inheritance_allowed("gearbox_speeds", source, target, POLICY)
        self.assertTrue(result["blocked"])


if __name__ == "__main__":
    unittest.main()
