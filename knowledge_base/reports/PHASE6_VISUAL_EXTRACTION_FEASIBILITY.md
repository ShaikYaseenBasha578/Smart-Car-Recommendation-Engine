# PHASE6_VISUAL_EXTRACTION_FEASIBILITY

## 1. Executive Conclusion
The feasibility spike concludes that a full OCR/CV pipeline is **NOT REQUIRED** for the vast majority of current extraction failures. By dropping down one level of abstraction to PDF-native characters (`page.chars`) and PDF-native vector graphics (`page.curves`, `page.rects`), we can deterministically recover Dzire, Virtus, Thar, and Scorpio without the hallucination risks or complexity of OCR. Tata EV brochures are simply inheritance lists, not matrices, requiring a separate textual parsing strategy. Only Maruti Alto K10 truly requires OCR, which should safely remain a `PDF_TEXT_FAILURE` rather than justifying a massive architectural leap.

**FINAL VERDICT:** FEASIBLE WITHOUT OCR  
**RECOMMENDATION:** FIX CURRENT PDF-NATIVE EXTRACTION FIRST

## 2. Corpus and Target Brochures
Analyzed Models: Tata Nexon, Tata Tiago, Tata Nexon EV, Tata Tiago EV, Volkswagen Virtus, Maruti Dzire, Mahindra Thar, Mahindra Scorpio Classic, Maruti Alto K10.

## 3. Experiment 1 — PDF Graphics (VW Virtus / Tata Nexon EV)
- **Volkswagen Virtus:** The feature markings are entirely absent from `pdfplumber.extract_words()`. However, inspection of `page.curves` and `page.rects` on Page 9 reveals exactly 144 small circles (`width < 10`) representing "Standard" dots (`●`) and 141 small rectangles representing dashes (`-`). These align perfectly with the X-coordinates of the configuration headers.
- **Tata Nexon EV:** The "matrices" are actually horizontally flowing text blocks (e.g., "addition to creative..."). The background rectangles (width 971) indicate row shading, not columns.

## 4. Experiment 2 — Character-Level Extraction (Maruti Dzire)
- **Maruti Dzire:** `extract_words()` produces corrupted, interleaved text (`h d i e g t e h h l t b`) because negative coordinates and CropBox interactions break horizontal word grouping. 
- **Result:** Iterating over `page.chars`, grouping strictly by rounded `Y` coordinates, and sorting by `X0` perfectly reconstructed the strings: `VXI MT/AMTZXI MT/AMT` and `FEATURES LIST`. Character-level reconstruction completely solves the Dzire failure.

## 5. Experiment 3 — Mahindra Character Reconstruction
- **Mahindra Thar / Scorpio:** The extraction reported `AXT` and `LXT` for Thar.
- **Result:** Character-level extraction confirms the raw embedded font characters are literally `A`, `X`, `T` (Roboto-Bold). There is no kerning issue or merged ligature. The OEM PDF intrinsically holds `AXT` as the raw evidence.

## 6. Experiment 4 — Rendered-Page Analysis
- Rendering Virtus and Nexon pages to images confirms the visual presence of dots, dashes, and colored feature blocks. However, because these exact shapes exist as PDF-native mathematical primitives (`curves`/`rects`) and text, image processing (pixel analysis) is entirely redundant.

## 7. Experiment 5 — Minimum Viable Prototype
A scratch prototype (`exp5_prototype.py`) was built successfully integrating:
1. **Vector Checkmarks:** Mapped Virtus `curves` to 'Standard' and `rects` to '-' deterministically using spatial bounding boxes against feature rows.
2. **Char Reconstruction:** Recovered Dzire's corrupted text fields perfectly.
3. **Fail-Closed Semantics:** Blank cells were left as `None` (Unknown), and no powertrain/transmission was inferred without explicit text.

## 8. Multi-Page Findings
- Vector-based multi-page continuation is trivial: Page 10 of Virtus contains identical column X-centroids as Page 9. By passing the inferred column X-coordinates from the first page, subsequent pages can map their `curves`/`rects` to the exact same configurations without needing to re-extract headers.

## 9. Failure Modes
- **Vector-only Text (Maruti Alto K10):** The feature matrix on Page 5 contains 134 curves and 3 images, but **0 characters**. The text itself is drawn as Bezier curves. This page cannot be extracted without OCR. It will correctly and safely fail closed (`PDF_TEXT_FAILURE`).

## 10. Architecture Comparison A–E
- **A. PDF text only:** Misses Virtus (graphics) and Dzire (character spacing). Fails on Tata EV (needs list parser).
- **B. PDF text + character-level reconstruction:** Solves Dzire and Mahindra. Reliable, fast, excellent provenance.
- **C. PDF text + vector/graphics reconstruction:** Solves Virtus. Highly deterministic, 0% hallucination risk compared to OCR.
- **D. PDF text + vector/graphics + rendered-image:** Redundant. Image processing adds complexity without recovering more than architecture C.
- **E. OCR/CV fallback:** Solves Alto K10, but introduces massive complexity, slowness, and severe hallucination risks (e.g., misreading "1" as "I" in technical specs). Not justified for a single failing model.

## 11. Recommended Minimum Architecture
**Architecture C:** PDF text + character-level reconstruction + PDF vector/graphics reconstruction.

## 12. What Should NOT Be Built
Do **NOT** build a Computer Vision, OCR, or rendered-image pixel processing pipeline. Do **NOT** build a machine-learning layout detection model. 

## 13. Production DB Integrity Verification
- **Pre-Experiment SHA1:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- **Post-Experiment SHA1:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- No canonical records, observations, or variants were altered.

## 14. Clear Next-Step Recommendation
**FIX CURRENT PDF-NATIVE EXTRACTION FIRST.**
We should immediately upgrade `BorderlessVariantColumnMatrixStrategy` to utilize `page.chars` for text recovery (solving Dzire) and `page.curves/rects` for symbol recovery (solving Virtus). Additionally, we must create a new `VariantFeatureListStrategy` to handle Tata's text-based inheritance lists. Alto K10 should be allowed to fail closed.
