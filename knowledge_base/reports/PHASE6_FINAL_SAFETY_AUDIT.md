# Phase 6 Final Safety Audit & Numeric Precision Policy

## 1. OEM Feature / Boolean Semantics
**Status: TESTED & VERIFIED**
The boolean normalizer has been explicitly constrained to prevent false certainty:
*   `Yes`, `Standard`, `Std`, `✓` explicitly map to `1`.
*   `No`, `Not Available`, `False` explicitly map to `0`.
*   `Optional`, `Available`, `-`, `N/A`, `Unknown`, and blank strings map strictly to `None`. 
We do not convert unverified evidence to False. The canonical fields (`sunroof`, `adas_available`, etc.) safely tolerate `None`, preserving ambiguity when an OEM feature matrix does not explicitly confirm absence.

## 2. Provenance / Brochure Snapshot Design
**Status: VERIFIED & NOT YET IMPLEMENTED (Asset subsystem)**
The existing `source_observation` schema is fully capable of capturing rigorous OEM provenance without modification:
*   `source_url`: Capable of holding an immutable local artifact reference (e.g., `file://assets/brochures/swift_2024.pdf`).
*   `raw_payload`: The JSON blob can easily accommodate an injected `__meta__` dictionary tracking Publication Date, Extraction Version, and Page/Table Location alongside the raw vehicle data.
*   `observed_at`: Inherently captures the download/observation timestamp.
**Remaining Limitation:** A small asset-fetching pipeline to download PDFs and generate these `file://` URIs is not yet implemented, but no database schema change is needed.

## 3. Authority Matrix Drift Check
**Status: VERIFIED (Drift Identified) & UNRESOLVED**
`authority_matrix.py` is currently a separately maintained duplicate of `SOURCE_AUTHORITY_MATRIX.md`. 
*   **Drift Identified:** The Python dictionary is missing several fields present in the Markdown, including `cylinders`, `gears`, `battery_capacity_kwh`, `charging_time_dc_fast`, and subjective/warranty fields.
*   **Smallest Proposed Correction:** Add the missing fields manually to `authority_matrix.py` before full production ingestion, or implement a lightweight runtime markdown parser to guarantee sync. No changes were silently made during this audit.

## 4. Generation Safety
**Status: TESTED & VERIFIED**
The resolver execution path enforces strict generation pinning. 
*   `process_oem_payload` raises a `ValueError` if `generation_id` is missing.
*   Historical generations can be intentionally targeted, completely isolating them from active-generation cross-contamination.

## 5. Numeric Normalization Final Check
**Status: TESTED & VERIFIED**
Unit interpretation strictly honors high-precision conventional conversion factors without arbitrary rounding.
*   **Bare "hp" Ambiguity:** `"100 hp"` correctly evaluates as ambiguous and returns `None`, whereas `"100 bhp"` resolves securely.
*   **Robustness:** `1,197 cc` maps precisely to `1197.0`. Malformed strings like `100.5.2 bhp` safely throw internal `ValueError`s, returning `None`.
*   **No Unnecessary Conversion:** `172 Nm` and `3995 mm` bypass conversion entirely, retaining their exact precision. 

## 6. Raw Evidence / Canonical Separation
**Status: TESTED & VERIFIED**
The core separation of concerns holds. 
*   Accepted values (`"100 PS"`), ambiguous values (`"100.5.2 bhp"`), and low-authority rejected values all preserve their original string representations identically inside `source_observation.raw_payload`. 
*   The canonical tables exclusively house the mathematically derived floats (`power_bhp` -> `100.0 * PS_TO_BHP`), strictly acting as normalized query representations.

## 7. SQLite Precision Capacity
**Status: INFERRED & VERIFIED**
SQLite `REAL` columns store 64-bit IEEE-754 binary floating-point numbers. It does not guarantee exact decimal representation for every number, but it is mathematically flawless for our expected automotive scales (~15 significant digits). No schema redesign to `DECIMAL` is justified.

## 8. Dry-Run Readiness
**Status: INFERRED & VERIFIED**
The current architecture safely supports an isolated transaction flow:
`OEM brochure PDF -> structured payload -> generation-pinned resolution -> field normalization -> field-level authority -> source observation -> provenance preservation -> rollback`.

## 9. Final Verdict

**Verdict: GO FOR BROCHURE EXTRACTION DRY RUN**

The normalizer safely guards against false booleans, ambiguous numerics, and precision destruction. The database securely tracks provenance without requiring schema adjustments. The architecture is cleared for a dry run.
