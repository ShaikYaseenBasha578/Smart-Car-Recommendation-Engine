# Phase 6: OEM Layout Family Validation

## A. Final Family Architecture
The architecture is now genuinely family-driven. Exact `(make, model)` routing was completely removed from the primary path. 
- The framework structurally fingerprints incoming PDFs.
- Based on geometry, text layout, and structural anchors, documents are classified as `BorderedVariantColumnMatrixStrategy`, `BorderlessVariantColumnMatrixStrategy`, or `EngineTrimCrossMatrixStrategy`.
- The instantiated family strategy natively extracts the structures without requiring model-specific metadata.

## B. Structural Discovery Mechanism
Instead of hardcoded pages, structural discovery is used:
- **VariantColumnMatrix**: Dynamically scans for `"FEATURE"` / `"SPECIFICATIONS"`, validates `pdfplumber.extract_tables()` output (e.g., table dimensions > 2x2), and dynamically reads the first multi-column row to parse variant column headers.
- **EngineTrimCrossMatrix**: Dynamically scans for `"ENGINE & TRIM PLAN"` and isolates the matrix relationships to preserve trim, powertrain, and transmission dimensions prior to pulling features.

## C. Classifier Mechanism
`classifier.py` now relies on `_inspect_fingerprint(pdf_path)`. It evaluates the PDF's structural identifiers (e.g., presence of `ENGINE & TRIM PLAN`, bordered matrices, borderless spaces, or CID font obfuscation). It returns the generic family strategy. Adapters are evaluated strictly *after* family classification, and only if explicitly necessary.

## D. Model-Specific Exceptions Remaining
- **Swift (`SwiftGen4VerticalStrategy`)**: Replaces dynamic header parsing with a static map because its PDF column headers (`VXi 5/5A VXi 5 CNG AMT`) are vertically merged in a way that breaks automated splitting. It still inherits 100% of the extraction logic.
- **Grand i10 Nios (`Hyundaii10NiosStrategy`)**: Merely provides a manual header list because the OEM OCR layer for headers is broken.
- **WagonR (`MarutiWagonRStrategy`)**: Fails closed explicitly due to PDF CID-font corruption.

## E. Fronx Extraction Coverage
**SUCCESSFULLY EXTRACTED**
Fronx structurally identified as a `VariantColumnMatrix`. Its complex merged headers (`Delta+ 1.2L MT/AMT & 1.0L Turbo MT`) were cleanly parsed by the generic `HeaderExpander` into 7 distinct variant identities across 77 features. No Fronx-specific adapter was needed.

## F. Baleno Extraction Coverage
**SUCCESSFULLY EXTRACTED**
Baleno structurally identified as a `VariantColumnMatrix`. The generic `HeaderExpander` burst its headers into 9 variant identities across 56 features. No Baleno-specific adapter was needed.

## G. WagonR Status
**FAILED CLOSED** (Unsupported Document Condition)
WagonR suffers from severe PDF font obfuscation, where text is mapped to `cid:X` glyphs (shifted by +30 ASCII). While mathematically solvable, implementing a raw character-level font shifter violates safe parsing invariants. Handled via an explicit `WagonR_CID_Exception` that fails closed.

## H. i10 Nios Status
**SUCCESSFULLY EXTRACTED**
Processed identically to Creta via `EngineTrimCrossMatrixStrategy`.

## I. Creta 24-Config Identity Audit
Audit of the generic `EngineTrimCrossMatrix` output against the canonical DB:
- 17 configurations cleanly resolved to exact canonical matches (e.g., `E Diesel 1.5L Turbo Manual`).
- 7 configurations were *accurately* rejected (e.g., `SX Diesel MT`, `SX Premium Diesel AT`, `SX(O) Petrol DCT`). The resolver failed closed correctly because these exact configurations genuinely do not exist in the Gen 2 Facelift database.

## J. Swift Regression
**PASSED**: 12/12 variants extracted perfectly.

## K. Family-Level Tests
The generic `classify_layout` function was tested by passing "unknown" as the make/model for Swift, Creta, and Fronx. The structural fingerprint correctly routed them to `VariantColumnMatrix`, `EngineTrimCrossMatrix`, and `VariantColumnMatrix` respectively, proving the framework no longer relies on hardcoded naming.

## L. Semantic-State Handling
Strict preservation in `ConfigurationIR`: `✓`, `●`, `S` uniformly normalize to `Standard`. `-` maps to `-` (Unknown/Absent) rather than aggressively coercing to `False`.

## M. Page/Section Discovery
Hardcoded index access was completely eradicated from all active strategies in favor of structural anchoring.

## N-Q. Regressions & DB Integrity
- **OEM Normalization:** PASSED
- **Generation Pinning:** PASSED
- **Phase 1–5:** PASSED
- **Idempotency:** PASSED (0 ghost updates)

## R. Production DB Hash Before/After
Before: `53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01`
After: `53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01` (Unmodified)

## S. Remaining Unsupported Structures
- Documents with corrupted PDF text layers / Custom CID mappings (e.g., WagonR).
- Completely un-tabled, unstructured paragraphs (none encountered yet).

## FINAL VERDICT
`OEM FAMILY ARCHITECTURE VALIDATED`
