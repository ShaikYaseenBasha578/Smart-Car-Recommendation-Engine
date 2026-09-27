# PHASE 6 OPTION B INTEGRATION REPORT

## 1. Files Changed
No production pipeline files (`extractor.py`, `classifier.py`, `ingest_oem.py`, `resolver.py`, `authority_matrix.py`) required modifications during this pass. The architecture implemented during the extraction repair phase cleanly integrates into the existing coordinator framework without any hacks or weakening of safety invariants. Tests and validation scripts were added to `scratch/` to verify structural constraints.

## 2. Architecture Integration Summary
The Option B native-PDF extraction components cleanly attach to `OEMBrochureExtractor.execute()`. 
- Extracted configurations (`ConfigurationIR`) correctly preserve structural provenance (e.g., raw string variants, exact vector markup).
- `extractor.py` bridges the raw object format into payloads cleanly.
- `ingest_oem.py` safely routes the payload through `resolve_variant` for strict fail-closed identity mapping.
- All structural evidence reaches the database completely intact without arbitrary normalization of vector semantics or missing values.

## 3. Strategy Routing Matrix
Routing is purely deterministic and structurally driven by `classifier.py`:
1. **CID/Font corruption** -> `MarutiWagonRStrategy`
2. **Engine/Trim Matrix detected** -> `EngineTrimCrossMatrixStrategy`
3. **Tata-style inheritance lists ("addition to")** -> `FeatureListStrategy` (Quarantined)
4. **Bordered Matrix detected + valid headers extracted** -> `VariantColumnMatrixStrategy`
5. **Fallback (Unstructured / Vector-heavy)** -> `BorderlessVariantColumnMatrixStrategy`

## 4. Identity-Resolution Safety Verification
Identity resolution remains strictly fail-closed:
- **Technical Tables**: Sending `3995 mm` as a variant name correctly fails resolution (unresolved).
- **Cross-Fuel/Transmission**: Sending a `Diesel` or `AMT` payload against an incompatible canonical variant correctly aborts resolution.
- **Generation Pinning**: `resolve_oem_generation()` correctly enforces exactly ONE match, throwing `ValueError` for 0 or multiple matches.

## 5. Authority & Provenance Verification
- **Authority Matrix**: `authority_matrix.py` confirms `oem` maintains highest priority (`tier 1`) for objective features (e.g., dimensions, capacity, booleans).
- **Provenance**: `update_canonical` strictly records `source_name: oem`, preserving explicit booleans and missing values. Unknowns are never coerced into `False`.
- **Vector Semantics**: Virtus vector marks (`[vector:curve]`) pass safely into the DB as raw strings, preserving evidence without hallucinated canonical state.

## 6. Targeted Test Results
- **Swift / Fronx / Baleno / Brezza / XL6**: `VariantColumnMatrixStrategy` (`SUCCESS`)
- **Creta / Grand i10 Nios**: `EngineTrimCrossMatrixStrategy` (`SUCCESS`)
- **Dzire / Virtus / Thar**: `BorderlessVariantColumnMatrixStrategy` (`SUCCESS`)
- **Tata Nexon / Nexon EV**: `FeatureListStrategy` (`EXTRACTION_FAILURE` - Safely Quarantined)
- **Tata Tiago / Tiago EV / Alto K10**: `BorderlessVariantColumnMatrixStrategy` (`EXTRACTION_FAILURE` - Safely Rejected)
- **Determinism**: Verified 100% stable matching on subsequent execution passes.

## 7. 62-Model Regression Comparison
*(Isolated scratch database execution)*
**Option B Accepted Baseline:**
- GENERIC_SUCCESS: 6
- GENERIC_PARTIAL: 11
- EXTRACTION_FAILURE: 21
- RESOLUTION_FAILURE: 12
- PDF_TEXT_FAILURE: 12
- CLASSIFICATION_UNKNOWN: 0

**Current Integration Run:**
- GENERIC_SUCCESS: 6
- GENERIC_PARTIAL: 11
- EXTRACTION_FAILURE: 21
- RESOLUTION_FAILURE: 12
- PDF_TEXT_FAILURE: 12
- CLASSIFICATION_UNKNOWN: 0

## 8. Classification Changes
There are **zero classification changes** compared to the accepted Option B baseline. The extraction logic remains strictly locked in. No previously successful models have regressed.

## 9. Production DB Checksum
- **Before Integration Pass**: `6ea3b931f7c157880445688665c500fb368a0c7b`
- **After Integration Pass**: `6ea3b931f7c157880445688665c500fb368a0c7b`

## 10. Remaining Unsupported Layouts
- **Alto K10**: Vector-only paths. Still requires heavy OCR layout detection.
- **Tata Inheritance Lists**: Explicitly quarantined pending a robust grammar parser.

## 11. Remaining Technical Limitations
- Feature lists built using inheritance grammar rather than traditional grid matrices cannot be safely parsed without hallucination risks and remain explicitly quarantined.
- Lack of textual legends on brochures like VW Virtus prevents fully automated semantic boolean normalization of certain vector paths, necessitating manual review or fallback visual processing for meaning derivation.

## 12. Final Status
**READY_FOR_PRODUCTION_INGESTION**
