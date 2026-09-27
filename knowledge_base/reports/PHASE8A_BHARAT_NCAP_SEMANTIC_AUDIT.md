# PHASE 8A — BHARAT NCAP SEMANTIC AUDIT

> **Status:** SHADOW AUDIT COMPLETE  
> **Production DB Checksum:** e752ebde5b7f227140bedb319c6b9753a3fdbdde (Untouched)  

## 1. Source Discovery Completeness
The BNCAP index (`vehicle-safety-ratings`) contains exactly 37 official test links. Our crawler successfully discovered and fetched all 37, parsing the HTML pages and acquiring the official PDF Factsheets.

## 2. Safety Schema Completeness
The `safety_test` schema was overhauled to accurately represent all BNCAP-supplied data, eliminating unsafe assumptions:
- `test_period`, `year_of_publication`
- `tested_variant_config`, `body_type`, `crash_test_weight_kg`
- `protocol_version`
- `aop_score`, `cop_score` (Numeric)
- `aop_stars`, `cop_stars` (Explicitly scraped from schema.org `ratingValue`, NOT derived)
- `sat_summary` (Safety Assist Technologies extracted separately as explicit text)
- `factsheet_url`, `artifact_path`, `artifact_checksum`
- `applicability_notes`

## 3. Source Artifact Inventory
Every test with an official PDF factsheet had its PDF downloaded to `scratch/bncap_pdfs/`. The SHA-256 checksum of each PDF is explicitly stored in `safety_test.artifact_checksum`, fulfilling the reproducible artifact requirement.

## 4. Provenance Architecture Integration
Instead of floating as isolated records, NCAP ingestion is now wired into the standard provenance system:
1. An official BNCAP `source_observation` (source_id=7) is created.
2. The entire parsed JSON payload is stored in `source_observation.raw_payload`.
3. The `safety_test` table references this `source_observation_id` as its anchor.

## 5. Entity Resolution & Alias Removal
We removed all unsafe heuristic mappings. Tests were matched strictly or via the explicit, documented, and evidence-grounded alias table `BNCAP_ALIAS_TABLE`.
*   **RESOLVED:** Tests clearly mapped to a single model.
*   **FAMILY_LEVEL:** e.g., Safari/Harrier explicitly states coverage of both models.
*   **UNRESOLVED:** Quarantined ambiguity.
*   **NO_MATCH:** Future/missing models (Basalt, VF6, Tekton, Invicto, etc.).

## 6. Applicability Scope Corrections
**CRITICAL FIX:** `MODEL_LEVEL` no longer forces `variant_id` population. The `safety_test_applicability` schema now correctly attaches the test to the `model_id` with `match_confidence = 'MODEL_LEVEL'` (or `FAMILY_LEVEL`). `variant_id` remains NULL in these cases.

## 7. True Shadow Diff
Logical snapshots were computed using exact row hashing before and after Pass 1:
- `safety_test`: +37
- `safety_test_applicability`: +27
- `source_observation`: +37
- `manufacturer`, `model`, `generation`, `variant`, `field_provenance`: +0

## 8. True Idempotency (Pass 2)
Running the exact same ingestion immediately after produced:
- 0 additions, 0 deletions, 0 modifications across ALL tables.

## 9. Exception Handling
Exceptions during URL fetching are caught with explicit retries. If unrecoverable, the script logs the failure but does not silently swallow DB errors. Rollbacks correctly trigger on DB insertion failure.

## 10. Remaining Blockers
None. 

## FINAL VERDICT: READY_FOR_BHARAT_NCAP_PRODUCTION
