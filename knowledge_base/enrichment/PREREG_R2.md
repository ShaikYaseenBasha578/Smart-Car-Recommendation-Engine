# Round 2 pre-registration (Flash extraction pilot)
Committed before any round-2 agy call. After this commit the instruction, filter, mapping, scorer and
thresholds do not change. A purely mechanical bug found later is fixed, and both the BEFORE and AFTER results are reported.

## What is fixed
- **Gold set:** `results_r2/gold.tsv`, 80 cells over 12 pages and 11 brochures. It keeps the round-1 40.
  - Page source: OCR 43, text 37. Layout: matrix 27, list 30, spec 23 (layout judged per page+field from page text before any call).
  - Fields: km/l 19, km/kg 4, cruise 32, wireless 18, paddle 7.
- **Truth set:** all 192 brochure-verified 10E–10N OEM cells for the 5 fields (`scratch:truth.json`).
- **Prompts:** `make_prompts_v2.py`, with the instruction verbatim from the brief plus the same field-meaning lines as round 1.
  The 12 prompt files hash to `19821dc218321ac5a29d74b061ec59b15293e548` (SHA-1 of the sorted per-file SHA-1 list).
- **Filter, mapping, scoring, metrics and decision:** `filter_score_v2.py`. Its docstring is the specification.
- **Run:** `run_round2.sh`: one call per page through `ask_gemini.sh` (isolation unchanged), with a round cap of 40 calls.
- **Index:** `build_index.py` + `ocr.swift`, giving `p<N>.words.json` in normalised page coordinates (0..1, origin top-left).
  Words come from pdfplumber on text pages, Vision on OCR pages, and Vision then pdfplumber on text+ocr pages.

## Decision table (as coded)
| condition | decision |
|---|---|
| CORRECT+WRONG among passing rows < 40 | INCONCLUSIVE → ALL-CLAUDE |
| P ≥ 0.95, Wilson LB ≥ 0.90, pass rate ≥ 0.50 | HYBRID |
| P ≥ 0.95, LB ≥ 0.90, pass rate < 0.50 | HYBRID-LIMITED on the page types (source × matrix/non-matrix) where P ≥ 0.95 and LB ≥ 0.90 hold on their own; if none qualifies → ALL-CLAUDE |
| otherwise | ALL-CLAUDE |

## Choices I made (not in the brief), fixed here
- Rows are scored after the per-trim split.
- UNKNOWN (no truth) and AMBIGUOUS (mapping) passing rows are excluded from precision and listed.
- km/l excludes CNG variants unless CNG is named, and includes ALLGRIP variants only if ALLGRIP is named.
- km/kg is restricted to CNG variants, and needs a gearbox like km/l.
- Trim keys ignore case and spaces ("HX 5" = HX5). Engine, paint and pack tokens are stripped from KB names.
- No aliases: "X+" ≠ "X Plus".
- Gearbox words in a header are naming, not qualifier markers.
- FOUND requires a CORRECT passing row.
- Tolerances: TY 0.004, TX 0.003, run gap 0.010.

## Mechanical self-test (synthetic rows written by hand from page text; no agy output used)
`results_r2/selftest_rows.tsv`:
- Correct: Taigun Highline "(AT only)" passes → CORRECT; Syros HTK+ section → CORRECT; Victoris "Zxi / Zxi (O)" 6AT splits into 2 rows → UNKNOWN.
- Wrong: Victoris Lxi claimed for 6AT → (d) rejects; Zxi with no qualifier → (e) rejects; Taigun Comfortline → (c) rejects; UNSURE rejected.
- Fixed during the self-test, before this commit:
  - quote spans use containment;
  - the qualifier "line" is defined geometrically;
  - text+ocr pages carry pdfplumber words too.
  None of these depended on any Flash output.

## File hashes at pre-registration
```
68b1dae1b8a68eb700edfaad285cb66503fd542d  make_prompts_v2.py
23907b6c1119c27ffe8f55456c73359858c552cf  make_prompts.py
8f9e940f6e54a2ab416d10a59012f8892c2a6de7  filter_score_v2.py
290ae93b46bf03763ec807ae1a0c6d098befcc2c  build_index.py
9964575c0825e6d7a801f2c86af868e545bb8ebb  ocr.swift
6d44c63382b1c7de3ffd640948e457fe81f20fd7  make_gold.py
d10b3c484c4f62989bddcef2d6c874a4cf8e5ede  ask_gemini.sh
ad474d27c7da7901f578ae8fbd1dfc8358d80ca5  run_round2.sh
a7afe3a653c70350c5410e5af86175e89efb358f  results_r2/gold.tsv
80b38584aebea89e78aae738d8f74677df83bc7a  scratch:truth.json
```
