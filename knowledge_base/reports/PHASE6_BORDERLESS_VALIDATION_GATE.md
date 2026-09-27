# PHASE6_BORDERLESS_VALIDATION_GATE

## 1. Executive Verdict
**FAIL / FIX BEFORE PROCEEDING**

**Decisive Reason:** While the `BorderlessVariantColumnMatrixStrategy` safely fails closed to protect data integrity, the fundamental premise of pure textual coordinate clustering is insufficient for the remaining corpus. Models like Tata Nexon/Tiago and VW Virtus use vector graphics (colored boxes or non-textual SVGs) for checkmarks that `pdfplumber` cannot extract. Models like Maruti Dzire use complex crop-boxes with extreme negative coordinates that interleave text when sorted. The spatial logic is deterministic but cannot process features hidden in the visual layer.

## 2. Architecture Audit Findings
- **Row/Column Clustering:** Safely identifies sparse columns but relies heavily on the presence of textual strict symbols (`S`, `-`, `✓`).
- **Coordinate Normalization:** Discarding negative coordinates masked Dzire's matrix. Keeping them revealed overlapping/interleaved text streams resulting in gibberish text concatenation. 
- **Header Detection:** The previous `_is_structural_trim` was dangerously loose. It has been hardened to reject transmission flags, english words, and dimensions.
- **Fail-Closed:** The architecture now strictly fails closed if headers are unidentifiable or boolean density drops below thresholds.

## 3. Powertrain/Transmission Audit
- **Previous State:** Hardcoded default to `Petrol MT`.
- **Action Taken:** Removed. The extractor now explicitly infers `Petrol/Diesel/EV` and `MT/AT/AMT` ONLY if explicitly present in the detected raw header name (with `AMT` checked before `AT`). Blank cells default to `None`. 
- **Tests Added:** `test_powertrain_transmission_inference` verifies safe inference mapping.

## 4. Structural Identity Validation
| Model | Expected Headers | Observed Headers | Status |
| :--- | :--- | :--- | :--- |
| **Thar** | AX Opt, LX | `['AXT', 'LXT', 'AXT', 'LXT']` | **TRUNCATED/MERGED** (Kerning merged 'AX' and 'T') |
| **Scorpio Cl.** | Classic S, Classic S11 | `['Variable Geometry', 'Common Rail Direct', 'Classic S', 'Classic S11']` | **SHIFTED** (Grabbed engine specs directly above headers) |

## 5. Feature-Column Validation
**Dzire (Negative Coordinates):**
* Feature: `W H W`
* Value: `h d i e g t e h h l t b ( m ( a m s m e m ) ( ) mm)`
* **Status:** Complete failure. Text is visually aligned but stored out-of-order with extreme negative X/Y offsets, breaking spatial X-sorting.

**Thar (Checkmark Spatial):**
* Feature: `Dual Tone Bumpers` -> Value: `✘`
* Feature: `LED Tail Lamps` -> Value: `✓`
* **Status:** Success. Valid column assignment.

## 6. Multi-Page Validation
Multi-page continuation was successfully implemented by clustering page-matrices that share identical column counts and matching X-centers (`< 25` point diff). However, since Virtus and Tiago fail closed on Page 1 due to missing vector text, multi-page is only demonstrable on Thar/Dzire.

## 7. Fail-Closed Validation
The tightened spatial rules successfully rejected non-matrices:
- **Alto K10:** FAILED CLOSED (Image-only / Vector text layer).
- **Virtus:** FAILED CLOSED (Vector checkmarks, no textual strict symbols).
- **Tata Nexon / Nexon EV:** FAILED CLOSED (Background color delimited, no text symbols).
- **Tata Tiago / Tiago EV:** FAILED CLOSED.

## 8. Real-Corpus Results Table
| MODEL | CLASSIFIER | STATUS | CONFIGS EXTRACTED | FAIL-CLOSED REASON |
| :--- | :--- | :--- | :--- | :--- |
| **Scorpio Classic** | Borderless | SUCCESS | 4 | - |
| **Thar** | Borderless | SUCCESS | 4 | - |
| **Alto K10** | Borderless | FAILED | 0 | Could not structurally locate... |
| **Dzire** | Borderless | SUCCESS | 12 (Garbage) | - |
| **Nexon** | Borderless | FAILED | 0 | Could not structurally locate... |
| **Nexon EV** | Borderless | FAILED | 0 | Could not structurally locate... |
| **Tiago** | Borderless | FAILED | 0 | Could not structurally locate... |
| **Tiago EV** | Borderless | FAILED | 0 | Could not structurally locate... |
| **Virtus** | Borderless | FAILED | 0 | Could not structurally locate... |

## 9. Tests Added
- `test_powertrain_transmission_inference`: Asserts no fabricated metadata and safe AMT/AT fallback.
- `test_negative_coordinates`: Proves negative coordinate capability.
- `test_raw_symbol_preservation`: Verifies symbols are not overwritten as `"Standard"`.

## 10. Production DB Integrity
- **Pre-execution SHA1:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- **Post-execution SHA1:** `6ea3b931f7c157880445688665c500fb368a0c7b`
- Production DB remains untouched.

## 11. Remaining Known Limitations
1. Cannot extract vector graphics (Tata colors, VW dots).
2. Complex PDF CropBox translation interleaves string tokens.
3. Tight kerning merges spaces (e.g., `AX Opt` -> `AXT`).

## Recommendation
**FIX BEFORE PROCEEDING.** 
Do not attempt to scale this purely textual spatial strategy further. The brochures genuinely lack the PDF text nodes required for deterministic geometric extraction. The architecture must be expanded to include Computer Vision (OCR / Layout Analysis) to handle vector symbols and negative-space matrices.
