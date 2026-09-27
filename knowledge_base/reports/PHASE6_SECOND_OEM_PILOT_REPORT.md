# Phase 6: Automated Real-World Second-OEM Pilot

## A. Manufacturer/Model/Generation Selected
**Manufacturer:** Hyundai
**Model:** Creta
**Generation:** Gen 2 Facelift (2024)

## B. Why this document is a meaningful second-layout test
The Hyundai Creta brochure uses a layout entirely alien to the Maruti Swift document. Instead of a single vertical checklist matrix where features are mapped with symbols across all variants, Hyundai employs a complex two-dimensional cross-matrix on Page 12 (mapping engine/transmission groups to 9 trims) and separates the Technical Specifications onto Page 14. This tested the ability of the architecture to parse decoupled metadata (identity matrix vs specifications) into unified `ConfigurationIR` objects.

## C. Official Source Page URL
https://www.hyundai.com/in/en/find-a-car/creta/highlights

## D. Direct PDF URL
https://www.hyundai.com/content/dam/hyundai/in/en/data/brochure/creta.pdf

## E. Stored Artifact Path
`knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf`

## F. SHA-256
`d9ad9205b7a12f06ef965b6c5ad5f638731a7805fa83db3de0c884adf8d4deb9`

## G. Document Structure/Layout Analysis
- **Page Count:** 16
- **Identity Matrix (Page 12):** Engine and transmission (MT, iVT, AT, DCT) rows are intersected with trim headers (`E`, `EX`, `EX(O)`, `S(O)`, etc.).
- **Feature Matrix (Page 12):** Features listed vertically, mapped with `S` (Standard) or `-` (Absent) across the 9 trim columns.
- **Technical Specs (Page 14):** Dimensions and Engine Displacement/Power/Torque grouped by `1.5l MPi petrol`, `1.5l U2 CRDi diesel`, and `1.5l Turbo GDi petrol`.

## H. Existing Strategy Suitability
Neither the `SwiftGen4VerticalStrategy` nor the generic `StandardMatrixStrategy` were suitable, as they rely on uniform line-by-line variants. The Creta document requires explicit mapping of the 2D matrix intersection and structural engine context.

## I. New Strategy Created
Created `knowledge_base/ingestion/oem/extractor/strategies/hyundai_creta_2024.py`.
It explicitly targets Pages 12 and 14, extracting the raw text and parsing the token matrices securely without altering the generic OEM `extractor.py` framework.

## J. IR Semantic Results
- `S` and `●` were cleanly translated to `Standard`.
- `-` was correctly preserved as `-`.
- Downstream boolean normalizer successfully processed `Standard` -> `1`, and left `-` as `None` (Unknown/Absent).

## K. Configuration Identity Method
Identity was explicitly built by tracing the structural intersection. The strategy tracked `engine_context` (e.g., `1.5 l MPi petrol`), associated it with the leading token (e.g., `MT`), and applied the row's `●` symbols to the corresponding columns (`E`, `EX`, etc.). Identity was not blindly regexed.

## L. Page/Section Discovery Method
The strategy uses hardcoded page indices (`pdf.pages[12]` and `[14]`). While effective for this specific fixed-document release, future iterations should scan for structural anchors (e.g., `"Technical specifications"`) to prevent page-shift regressions.

## M. Extraction Results
Successfully extracted **24 distinct configurations** mapping engine, transmission, variants, specifications, and feature availability.

## N. Canonical Ingestion Results
- **Processed:** 24
- **Resolved:** 17 (variants successfully matched via the resolver to existing DB canonical variants)
- **Updates Applied:** Safely injected normalized Technical Specifications (e.g., `113.30` bhp, `1497.0` cc) into the isolated test database `powertrain` and `variant` tables.

## O. Provenance Validation
All extracted fields securely bypassed conflicts and maintained `field_provenance` under `source_id = oem`, confirming that explicit identity tracking propagates through the entire pipeline.

## P-T. Regressions and Idempotency
- **Swift Regression:** PASSED (12/12 Swift variants correctly processed via `SwiftGen4VerticalStrategy`).
- **OEM Normalization:** PASSED (`84.4 kW (115 PS)` successfully unified into `113.30` bhp).
- **Generation-pinning:** PASSED (Successfully verified explicit Gen 2 Facelift mapping).
- **Phase 1-5 Regressions:** PASSED (Legacy extraction, V3Cars, and integration tests passed).
- **Idempotency:** PASSED (Running the Creta pipeline twice on the isolated DB yielded 0 duplicated updates).

## U. Production DB Hash
**Hash Before:** `53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01`
**Hash After:** `53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01` (Unmodified)

## V. Remaining Limitations
- **PDF Extraction Limits:** Highly stylized brochures (e.g., Tata Nexon) lacking gridlines or consistent line breaks confuse automated table scrapers.
- **Page Anchoring:** Strategies still rely heavily on hardcoded page numbers.
- **Dynamic Headers:** Multi-line or hierarchical headers currently require manual strategy alignment.

## FINAL VERDICT:
**OEM EXTRACTION LAYER READY FOR NEXT MANUFACTURER PILOT**
