# PHASE6_NATIVE_PDF_ARCHITECTURE_DECISION

## 1. Corpus Classification
- **Volkswagen Virtus:** PDF-native vector markings mapping to text headers.
- **Maruti Dzire:** Extracted words order-corrupted; perfect integrity at the PDF character level.
- **Mahindra Thar:** Font characters literally read `AXT`; kerning merge hypothesis disproven.
- **Tata Nexon / Tiago (EV):** Feature inheritance lists, NOT matrices.
- **Maruti Alto K10:** Pure vector paths instead of text fonts. Genuine OCR requirement.

## 2. Document Geometry Taxonomy
Based on the corpus, we formally separate geometries:
- **A. BORDERLESS_VARIANT_COLUMN_MATRIX:** Textual bounding boxes without explicit table gridlines (e.g., Scorpio Classic).
- **B. CHARACTER_POSITION_MATRIX:** Requires raw character-level parsing (X0/Y bounds) due to complex negative bounding box overrides (e.g., Maruti Dzire).
- **C. VECTOR_MARK_MATRIX:** Configuration headers are text, but feature markings are vector graphics (e.g., VW Virtus).
- **D. FEATURE_INHERITANCE_LIST:** Horizontally flowing text listing added features by trim (e.g., Tata Nexon EV).
- **E. VECTOR_TEXT_DOCUMENT:** Text is drawn as curves/images; no characters present in the PDF layer (e.g., Alto K10).

## 3. Character Reconstruction Findings
`knowledge_base/ingestion/oem/extractor/utils/pdf_char_utils.py`
A generic character-level text reconstruction algorithm was built. It groups `page.chars` into logical rows using a 2.0 y-tolerance and orders characters strictly by their `X0` coordinates. By doing this, Dzire’s interleaved, negative-coordinate strings (e.g., `h d i e g t e h h l t b`) were perfectly reconstructed into `VXI MT/AMTZXI MT/AMT`. This mechanism is broadly applicable for extracting correct sequences regardless of visual/crop-box overlap.

## 4. Vector-Mark Findings
`knowledge_base/ingestion/oem/extractor/utils/pdf_vector_utils.py`
For VW Virtus, checkmarks exist natively as PDF curves (circles) and rects (dashes). A generic spatial detector was implemented that matches objects with `width < 15` and `height < 15` against candidate column centroids. The semantic state is preserved as `NULL` with `evidence_type = "vector"`, leaving the interpretation strictly to downstream structural processors without defaulting to "Standard".

## 5. Thar Identity Findings
Investigation of `page.chars` confirmed the underlying font string physically embeds `A`, `X`, `T` in Roboto-Bold. There is no kerning issue or truncation artifact. Therefore, we must preserve `AXT` exactly as the raw evidence. If `AXT` fails canonical resolution against the expected `AX Opt` variant, the resolution failure must be logged rather than inserting model-specific identity hacks into the extraction layer. 

## 6. Tata Feature-List Findings
Tata brochures express features as progressive additions (e.g., "addition to creative..."). The structure is generic across Tata EV lines but functionally orthogonal to matrix logic. A skeleton strategy (`FeatureListStrategy`) was stubbed. It must safely accumulate features hierarchically without inferring "not listed = False."

## 7. Alto K10 Findings
The feature matrix page contains 0 characters and 134 vector curves representing text glyphs. Since `pdfplumber` cannot natively map raw bezier shapes back to font characters without OCR, this geometry remains a hard `PDF_TEXT_FAILURE`. OCR is deliberately deferred to avoid hallucination risks until necessary.

## 8. Multi-Page Findings
Native-PDF components preserve configuration column identity across pages. In Virtus, Page 10 maintains identically spaced column centroids as Page 9. The new architecture passes established `X0` centroids to continuation pages, cleanly aligning vectors and character-reconstructed features across multiple PDF pages.

## 9. Proposed Architecture
**Option B Selected:**
- `BorderlessVariantColumnMatrixStrategy` (Main driver for purely text-based loose grids)
- Shared `pdf_char_utils.py` (Character reconstruction utility)
- Shared `pdf_vector_utils.py` (Vector graphics spatial mark utility)
- Separate `FeatureListStrategy` (For Tata inheritance strings)

This avoids creating a massive, unstable catch-all script and segregates unique document semantics while sharing core geometric utilities. 

## 10. Test Coverage
Added regression tests to `test_native_pdf_utils.py`:
- `test_character_reconstruction()`: Confirms Dzire's complex spacing reconstruction.
- `test_vector_mark_detection()`: Validates detection of `curves` and `rects` mapped to matrix centroids.
- `test_powertrain_transmission_safety()`: Ensures strict nil fallback for Petrol/MT.
- `test_thar_raw_identity()`: Enforces preserving raw `AXT` identities.
- `test_fail_closed_alto()`: Ensures char-reconstruction fails safely on 0-char vectors.

## 11. Production DB Integrity
- **Pre-Experiment SHA1:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- **Post-Experiment SHA1:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- Production tables and metrics remained exactly 100% stable.

## 12. Explicit Implementation Plan
1. Refactor `BorderlessVariantColumnMatrixStrategy` to utilize `reconstruct_text_from_chars`.
2. Integrate `detect_vector_marks` as a fallback when `extract_words()` yields empty boolean columns.
3. Build the core block-segmentation implementation for `FeatureListStrategy`.
4. Validate these new shared components against the 8 targets simultaneously via batch execution.

## 13. Deferred Work
- Machine Learning OCR/Computer Vision for `Alto K10` vector extraction.
- Cross-brand synonym normalization fixes (if `AXT` resolution fails).

## 14. Final Recommendation
The architectural segregation accurately respects the varying geometries embedded inside the OEM PDFs. Shared utilities maximize reusability while separate strategies protect against logic bleed and false assumptions.

**FINAL VERDICT:** ARCHITECTURE READY FOR IMPLEMENTATION

**NEXT STEP:** Proceed directly to implement the Option B architecture.
