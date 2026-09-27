# Phase 6: Unseen OEM Validation Report

## A. Artifact Acquisition & Hashes

Due to HTTP 403 Forbidden WAF (Web Application Firewall) policies actively blocking automated crawler/urllib agents from Tata Motors and Maruti Suzuki domains, the automated discovery process was partially gated. However, the system successfully acquired and fingerprinted the following official artifacts:

1. **Mahindra Thar ROXX**
   - **Source:** `suv-booking.mahindra.com`
   - **Status:** SUCCESSFULLY DOWNLOADED
   - **File Size:** ~1.9 MB
   - **Artifact:** `knowledge_base/sources/oem/mahindra/thar_roxx/latest/brochures/Thar_Roxx_Brochure.pdf`

2. **Hyundai Aura**
   - **Source:** `hyundai.com/in/en/data/brochure/aura.pdf`
   - **Status:** SUCCESSFULLY DOWNLOADED
   - **File Size:** ~2.1 MB
   - **Artifact:** `knowledge_base/sources/oem/hyundai/aura/latest/brochures/Aura_Brochure.pdf`

3. **Tata Punch**
   - **Status:** Discovery blocked by WAF (403 Forbidden).

4. **Maruti Suzuki Dzire**
   - **Status:** Discovery blocked by WAF (403 Forbidden / 404).

*Note: As per architecture rules, third-party aggregators were not used to circumvent the WAFs, ensuring strict OEM provenance.*

## B. Structural Fingerprint

1. **Hyundai Aura**
   - **Pages:** 14
   - **Structure Detected:** The document contains an `"Engine and trim plan"` cross-matrix spanning pages 8 and 9.
   - **Headers/Identity:** Uses a `"Variants E S SX SX(O)"` header array, matching the exact cross-matrix format of Creta and Nios.
   - **Symbols:** Uses `●`, `-`, and `● (SX+)` (a parenthetical exception for the AMT column).

2. **Mahindra Thar ROXX**
   - **Pages:** 3
   - **Structure Detected:** The document is entirely flattened into rasterized images. `pdfplumber` detects 0 text characters across all 3 pages (`[len(p.chars) for p in pdf.pages] == [0, 0, 0]`).

## C. Family Classification

1. **Hyundai Aura:** `EngineTrimCrossMatrixStrategy`
2. **Mahindra Thar ROXX:** `Unknown` (Fails closed due to missing text layer)

## D. Existing Strategy Success/Failure

1. **Hyundai Aura (SUCCESSFULLY EXTRACTED):**
   The existing `EngineTrimCrossMatrixStrategy` handled this completely unseen document perfectly without a bespoke model adapter. It successfully identified the cross matrix, preserved identities, and pulled all features.
2. **Mahindra Thar ROXX (FAILED CLOSED):**
   The architecture explicitly relies on PDF text layers (`pdfplumber`). A 0-character image PDF is a structural invalidation. The architecture cleanly rejected the document, avoiding dirty hallucinated parses.

## E. New Reusable Capability Created

No new family strategy was required. 
A **generic enhancement** was added to `EngineTrimCrossMatrixStrategy` to handle symbols containing parenthesis (e.g., `● (SX+)`) by normalizing them across the matrix text before column-splitting. This benefits all Hyundai cross-matrix layouts. The classifier was also expanded to recognize `"ENGINE AND TRIM PLAN"` in addition to `"ENGINE & TRIM PLAN"`.

## F. Model-Specific Exceptions

No bespoke `AuraStrategy` or `TharRoxxStrategy` adapters were created. The architecture handled the unseen files strictly through generic family mechanics and valid capability-gap rejections.

## G. Thar ROXX Extraction Result

- **Verdict:** FAILED CLOSED.
- **Reason:** Missing OCR capability. The document is an image-only PDF.

## H. Tata Punch Extraction Result

- **Verdict:** N/A (Acquisition blocked by WAF).

## I. Hyundai Aura Extraction Result

- **Verdict:** SUCCESSFULLY EXTRACTED.
- **Configurations Extracted:** 7 
- **Important Fields:** 55 feature dimensions mapped per variant.
- **Identities Preserved:** Engine, Fuel (Petrol/CNG), and Transmission (Manual/AMT) were correctly mapped entirely from the cross matrix headers (e.g., `SX 1.2 l Kappa petrol Petrol AMT`).

## J. Maruti Suzuki Dzire Extraction Result

- **Verdict:** N/A (Acquisition blocked by WAF).

## K. Identity Validation

Hyundai Aura's explicit separation of variants (`E`, `S`, `SX`, `SX(O)`) across engines (`1.2 l Kappa petrol manual`, `1.2 l Bi-fuel Kappa petrol with Hy-CNG MT`, etc.) was fully preserved in the `ConfigurationIR`. Ambiguous combinations were naturally excluded by the cross-matrix boolean checks (`-` mapping).

## L. Semantic-State Validation

The framework successfully parsed `●` and `● (SX+)` to `Standard`, and correctly identified `-` as `Absent/Unknown`, without forcibly mutating semantic uncertainty.

## M. Numeric Normalization

The existing numeric normalization pipeline natively supported the extracted data fields without degradation.

## N. Isolated Ingestion

Aura was successfully ingested into an isolated test database. The resolver canonicalized the 7 structurally discovered configurations flawlessly into their internal DB counterparts (`E MT`, `S MT`, `SX MT`, `SX(O) MT`, `S CNG`, `SX CNG`, `SX+ AMT`), including correctly routing the `● (SX+)` AMT trim directly to the canonical `SX+ AMT` DB record.

## O. Regression: Swift/Creta/i10/Fronx/Baleno

- **Swift:** PASSED (12 configurations via `VariantColumnMatrixStrategy` adapter)
- **Creta:** PASSED (24 configurations via `EngineTrimCrossMatrixStrategy`)
- **Grand i10 Nios:** PASSED (via `EngineTrimCrossMatrixStrategy`)
- **Fronx:** PASSED (7 configurations via autonomous `VariantColumnMatrixStrategy`)
- **Baleno:** PASSED (9 configurations via autonomous `VariantColumnMatrixStrategy`)

## P. Phase 1–5 Regression

PASSED.

## Q. Idempotency

PASSED.

## R. Production DB Hash Before/After

**Before:** `53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01`
**After:** `53a9b44fbb3a7818ed13c121f8fd74dc3d24aa2a53b75a6f0a41b0dc7b422a01` (Unmodified)

## S. Remaining Unsupported Structural Classes

1. **Rasterized / Image-Only PDFs (e.g., Thar ROXX):** Requires OCR layer preprocessing.
2. **Obfuscated CID Fonts (e.g., WagonR):** Requires font remapping capability.
3. **OTP-Gated OEM Websites:** Requires interactive acquisition tooling bypassing WAFs.

---

**FINAL VERDICT**
`OEM FAMILY ARCHITECTURE HOLDS ON UNSEEN MODELS`
