# Phase 10C-1: OEM brochure extraction spot-check

**Purpose:** decide whether the OEM brochure extractions can be trusted, by having a human verify a sample against the source PDFs.

**Why it matters:** the Phase 10B W4 re-attribution gave 99 canonical cells a second corroborating source (OEM). That gain is provisional until this check passes. Phase 10A B2 already found junk values (`'Standard'`, `'[Vector:Curve]'`) and garbled observation names ("V O O", "SV - - -").

**Files:**
- `OEM_SPOTCHECK_SHEET.csv`: the sheet to fill in, 49 rows.
- `build_oem_spotcheck.py`: the exact, re-runnable sampling script.

**How the sheet was built:**
- Read-only, from a `/tmp` copy of production at SHA-1 `df9e2d9b391aa1b50edc42e27ccd63911345adf5`. Production was not opened for writing. No repo script was run.
- **No PDF was parsed.** Nothing is pre-filled.

## Sample
The population is every `field_provenance` row on the 52 OEM observations (`source_id=6`, `source_url='offline_brochure'`, ids 3669–3720): 133 rows in total, 104 confirmed, 28 rejected and 1 accepted.

| Stratum (`stratum` column) | Rows | How chosen |
|---|---|---|
| `REJECTED_WOULD_FLIP` | 28 | All rejected rows. These are the 10A B2 set that would flip to accepted if OEM were re-tiered to tier 1. |
| `CONFIRMED_SAMPLED` | 20 | Stratified random sample of the 104 confirmed rows (method below). |
| `ACCEPTED` | 1 | The only accepted row: paddle_shifters = 0 (provenance 37296, Skoda Kylaq variant 669 "Classic Petrol Turbo Manual"). |
| **Total** | **49** | across **10 distinct PDFs** |

**Seed:** `20260928`, using Python's `random.Random(20260928)`.

**Confirmed-row sampling method:**
1. Group the 104 confirmed rows by model. That gives 9 models.
2. Shuffle the model order and each model's rows with the seed.
3. Pick round-robin, one row per model per pass, until 20 are chosen.

The result covers all 9 models: Creta 3, Aura 3, Swift 3, City 3, Brezza 2, Baleno 2, Kylaq 2, Fronx 1, Amaze 1. Re-running `build_oem_spotcheck.py` on the same DB state reproduces the sheet exactly.

## Columns
| Column | Meaning |
|---|---|
| stratum | Sampling stratum (see above) |
| provenance_id / observation_id | `field_provenance.id` / `source_observation.id` |
| model, variant_id, variant_name | Canonical variant the observation was resolved to |
| observation_raw_name | The column/trim label the extractor read. Garbled names such as "V O O" are data, not typos. |
| field | Canonical field. 0/1 means absent/present for feature fields. |
| extracted_value | Value the extractor produced from the brochure |
| current_canonical_value | Current value in `variant`, a raw audit read |
| decision | What the updater did: confirmed = matched canonical; rejected = lost the authority check; accepted = filled an empty field |
| pdf_path | Brochure for that model, taken from `knowledge_base/sources/oem/brochure_manifest.json` |
| page_numbers | **Blank.** Page numbers were not recorded at extraction time. |
| **true_value** | *You fill in:* the value the PDF states for this variant and field |
| **verdict** | *You fill in:* `CORRECT` / `WRONG` / `NOT_IN_PDF` / `AMBIGUOUS` |
| **notes** | *You fill in:* page number, wording, anything unusual |

Caveats:
- **pdf_path is inferred.** The observations store only `offline_brochure`, not the file used. The path is the manifest's brochure for the variant's model, and each model has exactly one entry.
- **Kylaq's PDF is from CarTrade, not the OEM site.** It lives under `brochures/cartrade/`, so a failure there could be a source problem rather than an extraction problem. Record that in `notes`.

## How to fill in the sheet
1. Open the PDF and find the variant (trim) column that `variant_name` corresponds to. `observation_raw_name` shows what the extractor read, which may be garbled.
2. Find the row for `field`. Feature fields: tick, "Standard" or "●" = 1; dash, "–" or not offered = 0.
3. Write what the PDF says in `true_value` (0, 1, or the literal text), then set `verdict`:
   - **CORRECT:** `extracted_value` equals `true_value`.
   - **WRONG:** the PDF clearly states something different from `extracted_value`. This includes junk such as `'Standard'` or `'[Vector:Curve]'` when the real value is 1/0, and values read from the wrong trim column.
   - **NOT_IN_PDF:** the brochure does not cover this field for this variant, or this variant at all.
   - **AMBIGUOUS:** the PDF can be read more than one way (options pack, "(O)", footnote, AMT-only conditions). Explain in `notes`.

Judge the extraction, not the canonical value. `current_canonical_value` is for context only.

## How accuracy will be computed
Let C, W, N and A be the counts of each verdict.
- **Extraction accuracy (headline)** = C / (C + W). NOT_IN_PDF and AMBIGUOUS are excluded from the denominator and reported separately.
- **Coverage-adjusted accuracy** = C / (C + W + N + A). This is the conservative variant.
- Both are reported:
  - **overall** (49 rows);
  - **confirmed only** (20 rows): the value that matters for the W4 corroboration question;
  - **rejected only** (28 rows): the value that matters for any future OEM re-tiering;
  - the single accepted row, reported individually.
- Each rate gets a 95% Wilson interval. With n ≤ 28 per stratum, these intervals will be wide, and the report will say so.

**Decision rule, to be confirmed by the owner before scoring:**
- If confirmed-stratum accuracy is high, the W4 +1 corroboration stays.
- If it is low, a separate controlled write quarantines the OEM observations with reason `B2_OEM_EXTRACTION_REVIEW`, which removes that corroboration.
- No OEM value is promoted to canonical on the basis of this sample alone.
