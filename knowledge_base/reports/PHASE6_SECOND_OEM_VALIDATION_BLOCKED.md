# Phase 6: Real-World Second-OEM-PDF Validation Audit

## A. Artifact Status
**BLOCKED.** I performed an inspection of `knowledge_base/sources/oem/`. The only manufacturer directory currently present is `maruti_suzuki`, and the only model artifact available is the `Swift Gen-4 2024` brochure. 
*Action Taken:* As strictly instructed, I have stopped the validation process and did not download a random third-party brochure, nor did I manufacture a fake fixture to force a passing result. The next prerequisite is obtaining a real second-OEM artifact (e.g., Hyundai Creta, Tata Nexon).

## F. IR Semantic Audit Results
- **Checkmarks & Booleans:** `normalize_symbols()` correctly isolated checkmarks (`✓`) to the string `"Standard"`. Downstream, `field_map_oem.py`'s `normalize_boolean` intentionally maps `"standard"` to `1` (True). This is safe and semantically accurate for OEM documents.
- **Dashes & Blanks:** Dashes (`-`) are safely preserved through extraction. In `normalize_boolean`, `-` currently resolves to `None` (Unknown) rather than `0` (False). This is an intentionally conservative decision—it prevents accidental false-negatives from visual styling choices—but may need review if an OEM uses `-` to explicitly declare a feature stripped.
- **Conditions:** `apply_condition()` cleanly handles structural anomalies like `(AMT only)` by returning `-` (which maps to `None`) for non-matching configurations.

## G. Configuration Identity Audit
- The `StandardMatrixStrategy` fixture logic heavily relied on `if "CNG" in variant_name`. This is insufficient for production.
- Real documents do not guarantee variant strings will self-contain their exact transmission or fuel typologies. They frequently separate them into distinct matrix columns (e.g., `MT` | `AMT` | `DCT` columns) or use varying nomenclature (`iMT`, `EV`, `Hybrid`). Future layout strategies must explicitly map identity coordinates from the table structure rather than regex-guessing from a single cell.

## H. Page/Section Discovery Behavior
- Current strategies (`SwiftGen4VerticalStrategy`) rely on hardcoded zero-indexed page numbers (e.g., Page 5). This is fragile. If Maruti inserts an extra promotional page in a V2 brochure release, the strategy will fail. 
- Production strategies should employ structural scanning (e.g., iterating pages until the text "TECHNICAL SPECIFICATIONS" appears as a major table block).

## P. Final Readiness Assessment
The generalized architecture is built, but its resilience cannot be mathematically verified without an actual, complex second layout. 

**Next Prerequisite:** Obtain an official OEM brochure from a materially different manufacturer to execute the second-layout generalization pilot.
