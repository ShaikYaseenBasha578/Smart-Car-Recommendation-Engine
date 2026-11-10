# Flash extraction pilot, round 2: STOPPED at step 6 (blind check 93.3% < 95%)
Date: 2026-11-11 · branch `kb/enrich-flash` · pre-registration commit **db6de5d** · read-only on prod.

**No decision is issued.** The brief says to stop before the decision when blind agreement is below 95%.
For the record, the pre-registered scorer computed **INCONCLUSIVE → ALL-CLAUDE**: only 6 passing rows have
truth, against the 40 required. The two disputed rows cannot change that (see §6).

## 0. Access [VERIFIED]
- No lsof holders and no `-wal`/`-shm` files, before and after.
- Prod SHA-1 `758310ea3ea1868dd94cebc9f9535b34719fd994` at the start and the end. Fresh byte copies match.
- Queries ran only on `prod/q.db`.

## 1. Index upgrade [VERIFIED `index/index.tsv`]
- Every page has `p<N>.words.json` in one coordinate convention: normalised 0..1, origin top-left, `x0,top,x1,bottom`.
  The convention is recorded in index.tsv.
- Word sources: pdfplumber `extract_words` (text pages, 278), Vision word boxes (OCR pages, 76), Vision then pdfplumber
  (text+ocr pages, 22, whose prompt also carries the text layer's tables).
- 19 brochures, 376 pages, 108 s.
- Round-1 page texts are unchanged, except one Victoris p16 OCR row, where "EXTERIOR" moved to its own row (4-dp boxes).

## 2. Gold set [VERIFIED `results_r2/gold.tsv`]
80 cells over 12 pages and 11 brochures. It keeps the round-1 40 and adds:
- Venue p20: 9
- Taigun p10: 6
- Creta p14: 3
- City p13: 4
- Amaze p27: 3
- Harrier p18: 5
- Harrier p19: 5
- Victoris: +3
- Syros: +2

Composition:
- Page source: OCR 43, text 37.
- Layout: matrix 27, list 30, spec 23.
- Fields: km/l 19, km/kg 4, cruise 32, wireless 18, paddle 7.
- Yes/no values: 1 = 34, 0 = 23.
- Truth set: all 192 brochure-verified 10E–10N OEM cells for the 5 fields.

## 3–4. Instruction, filter and pre-registration
- The instruction is verbatim from the brief (`make_prompts_v2.py`).
- Filter (a)–(e), mapping, scoring and decision are in `filter_score_v2.py`; its docstring is the specification.
  Choices I made are listed in `PREREG_R2.md`.
- A self-test on hand-written synthetic rows (no agy output) found 3 mechanical problems. All were fixed **before** commit db6de5d:
  - quote spans now use containment;
  - the qualifier "line" is defined geometrically;
  - text+ocr words now include the text layer.
- Nothing in the instruction, filter, mapping, scorer or thresholds changed after db6de5d.
  I inspected all 110 rows and found no crash or parsing error to fix.

## 5. Run [VERIFIED `calls/index.tsv`, `results_r2/`]
- 12 calls (#013–#024), all SUCCESS, `authMethod=consumer`, no billing or API-key wording, no timeouts, no retries.
- 18.1 s wall per call on average (agy-reported 8.6 s).
- Calls used: **12 this round, 24 / 80 total**.

| | overall | text | OCR | matrix | non-matrix |
|---|---|---|---|---|---|
| rows (after per-trim split) | 110 | 13 | 97 | 74 | 36 |
| passing | 23 | 1 | 22 | 19 | 4 |
| pass rate | **20.9%** | 7.7% | 22.7% | 25.7% | 11.1% |
| passing with truth (C+W) | **6** | 0 | 6 | 3 | 3 |
| precision | **6/6 = 100%** | — | 100% | 100% | 100% |
| Wilson 95% LB | **61.0%** | — | 61.0% | 43.9% | 43.9% |
| UNKNOWN / AMBIGUOUS among passing | 16 / 1 | 1 / 0 | 15 / 1 | 15 / 1 | 1 / 0 |
| recall (gold FOUND) | **5/80 = 6.3%** | 0/37 | 5/43 | 3/27 | 2/53 |

- **Found:** Dzire ZXi MT 24.79; Dzire VXi CNG 33.73; Venue HX6 DCT cruise; Taigun Highline AT cruise; Taigun GT Line AT cruise.
- **Quotes:**
  - value_quote: 107 exact, 3 empty, **0 relabelled, 0 invented**;
  - header_quote: 101 exact, **7 relabelled, 0 invented**, 2 empty.
- **Qualifier misses (e):** 39 rows. 11 of them have values that are correct for their label.
- **Rejections:**
  - by check: e 27, d 25, d+c 15, d+e 12, c 4, a+b+d 3, b+d 1;
  - (d) reasons: header trim not located 29, no link / not nearest 13, no trim (UNSURE) 9, value not located 5.
- **Diagnostic, not used for any decision:** across all 110 rows, 35 map to variants with truth, and **all 35 are correct
  (0 wrong)**. The filter passed 6 and rejected 29. Flash returned UNSURE 9 times, for every model-level mileage line
  (Victoris, City, Amaze), which matches the instruction.

## 6. Blind check: 28/30 = 93.3% → STOP [VERIFIED `results_r2/blind_agreement.tsv`]
A fresh subagent saw only `blind_r2/`: the rules in prose, page text, words.json, variant names and 30 rows with opaque ids
(20 random passing, 10 random rejected, seed 20261111). It never saw the code, the gold set or truth.

**Disagreements (both on rule e):**
- **B10 = 013.9.1** (Venue HX 7 wireless "S"): the scorer rejected it on (e); the blind scorer passed it and judged it CORRECT.
- **B25 = 022.11.1** (Taigun Topline cruise "●"): the scorer passed it (verdict UNKNOWN); the blind scorer rejected it on (e).
- **B26** differs on (e) only; both reject it.

**Cause.** The pre-registered (e) takes "the value's line" around *every* quote span of value_quote. For a one-character
quote ("S", "●"), the containment span matches every word containing that character (the blind scorer counted 753), so the
outcome depends on markers anywhere on the page. The blind scorer used only the spans that form the (d) link. My code follows
the text as written, so this is a **specification ambiguity, not a mechanical bug**. Fixing it would be a design change, which
this round forbids, so I am reporting it rather than making it.

**Effect on the pre-registered outcome:** none. With the blind reading, B10 adds one CORRECT (7 with truth) and B25 is UNKNOWN.
Both readings stay far below the 40-row minimum.

## 7. Syros 764 (read-only; rendered and visually confirmed)
- PDF SHA-1 `7622f531…` (`kia_syros_brochure.pdf`), p7 rendered at 300 dpi (`syros764/*.png` in scratch).
- The **HTX row "[Features in addition to HTK+ (O)]"** lists "Smartphone Wireless Charger" in its third column. That row has no
  "Automatic Only Features" heading (the HTK+ row has one; HTX does not).
- The powertrain table offers HTX only as 1.0 T-GDi **7DCT** and 1.5 CRDi **6AT**: ● in both, – for both 6MT rows.
- So per this brochure, **764 HTX Diesel Automatic should have wireless_charging = 1**. The KB has 0 (v6_migration, plus a v3cars
  zero with an empty feature list), while 763 HTX Petrol DCT = 1.
- This is a backlog candidate for a controlled write (P1 is now satisfied by this render). Nothing was written.

## Design changes a round 3 would need (reported, NOT made)
1. Rule (e): define "the value's line" around the value spans that form the (d) link only, or require value_quote to include
   its row label so a one-character quote is never the whole anchor.
2. Trim normalisation:
   - strip "Speed" (Creta "… CVT Speed Automatic" becomes trim "SX Premium Speed", so SX Premium CVT never maps);
   - pre-register aliases: "X+" = "X Plus", "Knight" editions, OCR "Zxit" = "Zxi+".
3. Headers printed over two lines ("Highline / Plus", "Comfort- / line", "GT Plus / Chrome") never form a contiguous trim span.
   This is the largest single cause: 29 "header trim not located".
4. Spec-block captions sit *below* their values (Ertiga "20.51 … / LXi MT, VXi MT …"), but COLUMN_HEADER requires the header above.
5. Model-level mileage (one figure per gearbox for all trims): the instruction forces UNSURE, so these cells can never be found.
   The brief would need to allow a gearbox-level label.

Even with all five changes, the round-2 rows would give at most 35 rows with truth (the diagnostic count), which is still below 40.
A round 3 needs more pages, as well as the fixes.

## Files
- Branch `knowledge_base/enrichment/`:
  - `PREREG_R2.md`, `filter_score_v2.py`, `make_prompts_v2.py`, `run_round2.sh`, the updated `build_index.py` / `ocr.swift` / `make_gold.py` / `ask_gemini.sh` (round cap only);
  - `results_r2/` (gold, rows, recall, calls, metrics, self-test, blind agreement).
- Scratch only: raw call JSON, agy logs (they contain the account email), prompts, index, renders and DB copies.
