# Phase 6 Variant Resolver Audit & Deterministic Fix

## 1. Exact Files Changed
*   `knowledge_base/ingestion/common/resolver.py`: Rewrote `compute_similarity`, `resolve_variant` alias lookup, and fuzzy candidate selection logic.
*   `knowledge_base/ingestion/oem/ingest_oem.py`: Added `source_name='oem'` parameter to `resolve_variant` calls to enable source-aware alias lookups.

## 2. Exact Resolver Decision Hierarchy
The resolver now enforces a strict, deterministic evaluation path:
1.  **Exact Alias Match:** If `variant_alias` holds an explicit, verified mapping for the provided `source_name`, it immediately maps to the canonical ID.
2.  **Structured Pre-filtering:** Variants are globally filtered by `generation_id` (must match exactly, no fallback) and by `validate_structured` (rejects mismatches on Fuel, Transmission, Engine CC bounds).
3.  **Exact Name Match (Highest Priority):** If the normalized canonical name directly matches the raw source name or slug, the loop short-circuits and resolves instantly.
4.  **Fuzzy Fallback (Identity Token Veto):** Words like `petrol`, `mt`, `cng`, `hybrid` are temporarily subtracted. If the remaining "identity" tokens (e.g., `lxi`, `vxi`) have exactly zero overlap, the score is forcefully cast to `0.0`, blocking cross-variant bleeding entirely. If they share identity, a standard string overlap is calculated over the *full* string to resolve internal configuration tiers (e.g., CNG vs Petrol).

## 3. Exact Ambiguity Rule
*   **Previous Behavior:** The system arbitrarily selected the first variant that tied for the highest fuzzy score.
*   **New Ambiguity Rule:** The resolver computes a minimum score-margin requirement. All viable candidates are sorted by score. If the difference between the Best Candidate (`best_score`) and the Second-Best Candidate (`second_best_score`) is less than `0.05`, the system **rejects the payload and returns `unresolved`**. Sibling trims and near-ties are now mathematically guaranteed to fail rather than silently cross-contaminating.

## 4. Alias Behavior Before/After
*   **Before:** The SQL query strictly hardcoded `WHERE s.name = '91wheels'`, meaning manual aliases for OEM or any other ingestion pipelines were completely ignored by the database. Furthermore, ingestion scripts manually inserted aliases into the DB upon failure.
*   **After:** `resolve_variant` was upgraded to dynamically query by `source_name` (e.g., `oem`). Explicit OEM aliases can now be respected if manually populated. Crucially, as per the rules, the resolver itself never automatically creates aliases from fuzzy matches.

## 5. Generation-Selection Behavior
*   OEM ingestion mandates strict generation pinning. The resolver applies `AND v.generation_id = ?` directly in the database query. There is no automated fallback to `active_only` or the "latest" generation if the specified generation is not found. Attempting to ingest a variant against the wrong generation safely returns `unresolved`.

## 6. Test Results
The test suite successfully executed 14 distinct scenarios against a temporary isolated database:
*   **LXi Petrol Manual:** Resolved to `LXi Petrol Manual` via exact match.
*   **ZXi+ / ZXi Plus:** Resolved correctly via standard token normalization (`+` -> `plus`).
*   **VXi CNG Manual:** Resolved to `VXi CNG Manual` (CNG identity disambiguation).
*   **Exact Alias Resolution:** Created test alias `zxi-extreme` -> mapped perfectly to `ZXi Plus Petrol Manual`.
*   **Sibling-Trim Confusion:** Submitting `LXi` successfully resolved to `LXi Petrol Manual` because `validate_structured` eliminated the CNG variant, leaving only one safe `0.8` candidate.
*   **Near-Tied Fuzzy Candidates:** Submitting `Petrol Manual` without a trim prefix resulted in multiple ties. Rejected successfully (`unresolved`).
*   **Wrong Fuel/Trans/Gen:** Pre-filtered safely by `validate_structured` -> `unresolved`.

**Regression Suite:** The Phase 1-5 legacy scripts (`test_extraction`, `test_v3cars`, `test_integration`) executed completely successfully with 0 failures.

## 7. Remaining Production Blockers
This audit was performed strictly on a code/simulation basis. The OEM payload was provided via simulated Python dictionaries. 
*   **Blocker:** There is currently no actual PDF Parsing module (e.g., `pdfplumber`, `pymupdf`, or Vision logic) built to extract a real brochure into this dictionary schema. 
Phase 6 OEM ingestion cannot be declared production-ready until an actual official OEM brochure PDF is ingested, parsed, and evaluated end-to-end.

## 8. Final Verdict
**RESOLVER VERIFIED**
