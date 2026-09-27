# Phase 6: Generalized OEM Brochure Extraction Architecture

## A. Swift-Specific Dependencies Identified (Pre-Refactor)
Prior to this generalization, the script `scratch/parse_swift_brochure.py` possessed the following hardcoded dependencies:
- **Structural Coupling:** Hardcoded to exact page indexes (Page 6), table counts, and strict row/column layouts characteristic only to the Maruti Suzuki Swift 2024 vertical brochure.
- **Identity Coupling:** Variant identification heavily relied on string replacement tailored to Swift nomenclature (e.g. `VXi 5MT/5AMT`, `ZXi+`).
- **Condition Coupling:** Explicitly stripped out specific Maruti terminology like `(AMT only)` and `CNG Only` within the core loop.

## B. Generalized Architecture Implemented
A modular, strategy-based abstraction layer has been constructed to safely scale OEM ingestion across multiple manufacturers and layouts:
1.  **Intermediate Representation (IR):** `ConfigurationIR` and `ExtractedField` preserve exact raw values, source page location, structural section, and applicability conditions independently from the database schema.
2.  **Layout Strategy Pattern:** Abstract class `OEMBrochureLayoutStrategy` mandates that layout-specific rules are siloed into designated strategies (e.g., `SwiftGen4VerticalStrategy`, `StandardMatrixStrategy`).
3.  **Extractor Coordinator:** `OEMBrochureExtractor` acts as the bridge. It executes the provided strategy to yield the IR and automatically transforms it into the normalized dictionary payload format that `process_oem_payload` requires.
4.  **Reusable Utilities:** Shared logic for symbol resolution (✓, -) and powertrain/transmission conditionals (`AMT only`) have been abstracted into `utils.py`.

## C. Files and Modules Created or Modified
**Created:**
- `knowledge_base/ingestion/oem/extractor/base.py` (IR definitions & `OEMBrochureLayoutStrategy` interface)
- `knowledge_base/ingestion/oem/extractor/extractor.py` (`OEMBrochureExtractor` pipeline wrapper)
- `knowledge_base/ingestion/oem/extractor/utils.py` (Symbol normalization, condition evaluations, pdfplumber wrapper)
- `knowledge_base/ingestion/oem/extractor/strategies/swift_2024.py` (Siloed Swift specific strategy)
- `knowledge_base/ingestion/oem/extractor/strategies/standard_matrix.py` (Generic horizontal matrix strategy)

**Modified:**
- `scratch/run_oem_ingestion_v2.py` (Updated to execute the modular pipeline)

## D. Layouts Actually Supported
1.  **Maruti Suzuki Dual-Table Vertical Feature Matrix:** Specifically, the 2024 Swift Gen-4 structure where Tech Specs and Features List reside sequentially on the same page, with variant combinations grouped hierarchically across columns.
2.  **Standard Horizontal Matrix:** Standard single-table layouts where the Y-axis designates variants and the X-axis designates features (verified via `StandardMatrixStrategy`).

## E. Swift Regression Result
*   **Result:** PASSED
*   **Verification:** Re-executed the actual Maruti Suzuki Swift Gen-4 PDF through `SwiftGen4VerticalStrategy`. 12/12 variants resolved seamlessly.
    *   **Petrol (LXi):** 1197 cc, 80.46 bhp, 111.7 Nm securely extracted and matched.
    *   **CNG (VXi):** 1197 cc, 68.80 bhp (calculated from 51.3 kW), 101.8 Nm securely extracted.
    *   All Dimensions, Booleans, and features strictly mapped.

## F. Second-Layout Validation Result
*   **Result:** PASSED
*   **Verification:** A generic horizontal feature matrix fixture PDF (`fixture_matrix.pdf`) was constructed. `StandardMatrixStrategy` independently parsed it, correctly inferring powertrain properties (Base CNG MT, Mid Petrol AMT) and standardizing checkmarks (`✓`) to explicit booleans without inheriting any Swift-centric hardcoding.

## G. Unit/Normalization Regression Result
*   **Result:** PASSED
*   **Verification:** Reusable field normalization logic (`map_oem_fields` and `robust_parse`) remained completely detached from extraction. Power equivalencies (kW to bhp) successfully triggered the identical rigorous dual-conversion rules previously verified.

## H. Idempotency Result
*   **Result:** PASSED
*   **Verification:** Running the OEM pipeline iteratively upon the isolated DB resulted in strictly `0` duplicate updates, retaining canonical stability.

## I. Phase 1-5 Regression Result
*   **Result:** PASSED
*   **Verification:** All legacy source tests (`test_extraction.py`, `test_v3cars.py`, `test_integration.py`) passed cleanly (0 failures).

## J. Production DB Hash
*   **Hash Before Refactor:** `53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01`
*   **Hash After Refactor:** `53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01` (100% untouched).

## K. Known Unsupported Layouts / Limitations
- **Landscape Feature Matrices:** Brochures spanning horizontal wide-page formats with variant configurations spread across split tables are unsupported.
- **Unstructured / Fluid Brochures:** PDFs completely lacking table borders or strictly formatted bounding boxes (relying on raw visual whitespace) are unsupported by `pdfplumber` defaults and will require advanced bounding strategies.
- **Complex Hierarchical Headers:** Multi-tier headers where options are nested multiple levels deep outside of simple text blocks are currently untested.

## L. Conclusion
**READY FOR NEXT PILOT:** The OEM extraction layer successfully decouples extraction rules from normalization logic. By adhering to the `OEMBrochureLayoutStrategy`, the system is fully equipped to ingest the next manufacturer pilot (Hyundai, Tata, Mahindra) simply by defining the corresponding geometric layout strategy. No core architecture rewrites will be required.
