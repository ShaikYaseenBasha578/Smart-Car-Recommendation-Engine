# Phase 6 Post-Blocker Fix Report

## 1. Exact Files Changed

*   **[NEW]** `knowledge_base/ingestion/common/authority_matrix.py`: Created a declarative Python map for field-specific source authority tiers.
*   **[MODIFIED]** `knowledge_base/ingestion/common/updater.py`: Swapped the global `source.authority_tier` integer lookup for the dynamic `get_authority_tier(source_name, field)` function.
*   **[MODIFIED]** `knowledge_base/ingestion/oem/ingest_oem.py`: Enforced `generation_id` as a strictly required parameter and removed reliance on `active_only=True`.
*   **[MODIFIED]** `knowledge_base/ingestion/oem/field_map_oem.py`: Replaced the naive key-value map with a robust unit normalization engine targeting power, torque, capacities, and boolean semantics.

## 2. Exact Architectural Behavior Changed

*   **Authority Evaluation:** The updater no longer checks the `source` table for a global tier. It queries `authority_matrix.py`, meaning "OEM" is no longer universally trusted for every column. It only holds authority where explicitly granted by the matrix.
*   **Generation Constraints:** OEM payloads can no longer be blindly resolved against the active generation. They must explicitly declare their generation context before touching the resolver, closing a major data-pollution vector.
*   **Silent Data Corruption Prevention:** Passing "82 PS" or "100 kW" into the ingestion pipeline will no longer overwrite the canonical `power_bhp` field with the raw integer 82 or 100. It is now accurately converted via internal math or safely rejected.

## 3. Field-Level Authority Design

The declarative `FIELD_AUTHORITY` dictionary maps canonical fields to their preferred sources as defined in `SOURCE_AUTHORITY_MATRIX.md`. 
*   **Example:** `'power_bhp': {'oem': 1, '91wheels': 2, 'carwale': 3}`
*   **Example:** `'real_world_mileage_kmpl': {'team_bhp': 1, 'autocar_india': 2}`
*   If a source (like OEM) attempts to write to a field where it is not listed (e.g., `real_world_mileage_kmpl`), it is dynamically assigned Tier 99. The updater compares Tier 99 against the existing proven canonical backer (e.g., Team-BHP at Tier 1) and correctly rejects the OEM observation, preserving the existing truth.

## 4. Generation-Safety Design

`ingest_oem.py` now explicitly checks `if generation_id is None: raise ValueError(...)`. 
Furthermore, the `resolve_variant` call drops the dangerous `active_only=True` parameter. This means if we ingest a brochure for the discontinued 2021 Swift (Generation 3), the resolver will safely and exclusively bind to Generation 3 variants, rather than incorrectly fuzzy-matching the modern active Generation 4 variants that share identical names.

## 5. Numeric Normalization Design

A suite of specific normalization functions (`normalize_power`, `normalize_torque`, `normalize_engine_cc`, `normalize_dimension`, `normalize_capacity`) was implemented.
*   **Conversions:** Correctly converts `kW` (* 1.34102) and `PS` (* 0.98632) to `BHP`. Converts `cm` (* 10) to `mm`, and liters to `cc` for displacement.
*   **Ambiguity Rejection:** If a string is provided (e.g., "100") without an identifiable unit where units differ wildly, the mapper returns `None` to force the resolver to ignore it rather than guessing.
*   **Boolean Semantics:** Safely maps "Standard", "Std", "Yes", "✓" to `1`. Maps "Optional", "Available", "No", "-" to `0`, preserving the rule that "Unknown != False" (Unknowns remain `None`).

## 6. Test Matrix & Results

An isolated SQLite testing script (`test_phase6_blockers.py`) was executed against a cloned representation of the database.

**Field-Level Authority:**
*   **PASSED:** OEM high-authority objective field (`boot_space_litres`) successfully overrides lower-tier 91Wheels objective field.
*   **PASSED:** OEM does NOT override a field where OEM has no authority (`mileage_arai_kmpl` vs `team_bhp`).
*   **PASSED:** Lower-tier conflicting evidence remains preserved as `rejected` in `field_provenance`.
*   **PASSED:** Equal-authority conflict deterministically falls back to first-in-wins.
*   **PASSED:** Identical values are properly logged as `confirmed`.

**Generation Safety:**
*   **PASSED:** Missing `generation_id` safely raises `ValueError` before making DB calls.
*   **PASSED:** Resolving a recycled variant name specifically to a historical discontinued generation works flawlessly without being hijacked by the active generation.

**Unit Normalization:**
*   **PASSED:** 100 PS -> 98.63 BHP. 100 kW -> 134.1 BHP. 
*   **PASSED:** "1.2 litres" displacement -> 1200.0 cc. "399.5 cm" -> 3995.0 mm.
*   **PASSED:** "Optional" -> 0. "Standard" -> 1. "Unknown" -> None.

## 7. Phase 1–5 Regression Results

A manual test runner successfully executed the existing pytest suite:
*   `test_extraction.py`: **PASSED**
*   `test_v3cars.py`: **PASSED**
*   `test_integration.py`: **PASSED**
*   `test_editions.py`: **PASSED**
Existing 91Wheels, V3Cars, and CarWale ingestion behavior remains intact and unaffected by the new field-level authority system.

## 8. Remaining Concerns

*   **PDF Pipeline Pending:** The actual `extractor_oem.py` still relies on a mock JSON dictionary. A real text/table parser (like `pdfplumber`) or an LLM vision pipeline must be integrated before it can read raw Maruti PDFs.
*   **Provenance Strategy:** `source_url` is currently hardcoded as `'offline_brochure'`. An asset management system must be established to store the downloaded PDFs locally and link their file paths to the DB.

## 9. Final Production Verdict

**Verdict: GO FOR MARUTI PILOT**

The KB architecture is now demonstrably safe. It protects historical generations, strictly enforces the field-level authority matrix, and prevents unit-driven data corruption. The foundation is ready for the first real brochure extraction.
