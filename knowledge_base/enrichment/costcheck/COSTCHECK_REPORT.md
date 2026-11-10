# Cost check: "Claude verifies Flash" vs "Claude extracts alone" (Sonnet, both arms)
Date: 2026-11-11 · branch `kb/enrich-flash` · pre-registration commit **64ea6a7** · read-only on prod.

## DECISION: **ALL-CLAUDE** (pre-registered rule, applied unchanged)
VERIFY used **31% more** total tokens than EXTRACT (ratio 1.31, a −31% saving), not ≤ 60%. It also made 4 wrong cells
where EXTRACT made 8. No page type met all four conditions, so there is no HYBRID-PARTIAL either.

## Setup [VERIFIED `PREREG_COSTCHECK.md`]
- 3 pages from round 2, Flash outputs reused (**0 new agy calls**; agy total stays 24/80):
  | key | type | Flash rows given to VERIFY |
  |---|---|---|
  | syros_p7 | text-layer grid (trims as row headers; no text-layer *matrix* page exists in the gold set) | 2 |
  | victoris_p16 | OCR / scrambled-layer page | 17 |
  | venue_p20 | tick-icon grid | 39 |
- PNG tiles: Syros 3 tiles at 140 dpi (1128×1260 px each); Victoris 1 page at 150 dpi (1240×1754); Venue a full page at 100 dpi (1500×1850) plus a
  header+Comfort&Convenience crop at 115 dpi (1565×767).
- 12 measured headless runs (3 pages × 2 arms × 2 repeats) plus 2 overhead-baseline runs.
- `claude -p --model sonnet … --restricted --tools Read`, one folder per run.
  Every run exited 0 with `is_error=false`, `err.txt` empty. Each folder held only its inputs plus out.json/err.txt/run.meta.
  The isolation canary (before freezing) refused reads outside the folder and had no shell or write tool.
- Truth: brochure-verified 10E–10N cells on these pages (Syros 19, Victoris 32, Venue 16).
  Cells without truth are UNKNOWN: 15 + 31 + 41 per run, 174 in each arm's 6 runs, never counted correct or wrong.

## Tokens [VERIFIED `score/runs.tsv`]
Gross total = input + cache_creation + cache_read + output (the decision uses this). Mean of 2 repeats per page.
| page (type) | EXTRACT | VERIFY | VERIFY/EXTRACT | saving |
|---|---|---|---|---|
| Syros (text-layer grid) | 22,589 | 32,258 | 1.43 | −42.8% |
| Victoris (OCR) | 37,942 | 44,254 | 1.17 | −16.6% |
| Venue (tick-icon grid) | 24,517 | 34,844 | 1.42 | −42.1% |
| **sum over 3 pages** | **85,048** | **111,357** | **1.31** | **−30.9%** |
- Net of the harness overhead (baseline 3,282 tokens per run): 75,202 vs 101,511, ratio 1.35.
- Mean output tokens per page: EXTRACT 6,515, VERIFY 7,658.
- Cost (JSON `total_cost_usd`, mean summed over pages): EXTRACT $0.332, VERIFY $0.419.
- Wall time per run (JSON `duration_ms`, mean): EXTRACT 35.1 s, VERIFY 40.8 s.
- Run-to-run spread is large in cache_read/creation (e.g. Syros VERIFY 23,457 vs 41,058 total), but the ordering holds on every page and repeat.

## Accuracy [VERIFIED]
Counted over all 6 runs of each arm (134 truth-cell instances).
| | correct | wrong | missed | qualifier errors | recall |
|---|---|---|---|---|---|
| EXTRACT | 126 | 8 | 0 | 0 | 94.0% |
| VERIFY | 130 | 4 | 0 | 0 | 97.0% |
- **All 12 wrong cells are one case:** Victoris Zxi+ and Zxi+ (O) AT ADAS / ALLGRIP, cruise_control. The page prints
  "Cruise Control … (MT & Strong Hybrid)" and an ACC row marked "6AT". The truth (10N) counts the adaptive cruise control as cruise_control = 1.
  Both arms answered 0 from the plain-cruise row, qualifier "MT & Strong Hybrid only". EXTRACT did this in both repeats; VERIFY did it in repeat 2.
  VERIFY repeat 1 got it right (32/32), and repeat 2 CORRECTED 7 candidates, so its verdicts are not stable.
- The wrong cells are an interpretation question, not an OCR or reading error. They are the same one the round-2 report flagged ("6AT qualifier"),
  and the same one that failed cruise in 10N's round 1.
- 0 qualifier errors in both arms with the pre-registered keys (Venue paddle/cruise, Victoris paddle/cruise). Both arms applied "DCT/AT only", "1.5 Diesel only" and "6AT" qualifiers.
- Both arms used the "missed" category 0 times: every truth cell got an answer.

## Conditions (pre-registered)
| condition | overall | Syros | Victoris | Venue |
|---|---|---|---|---|
| 1. VERIFY tokens ≤ 60% of EXTRACT | **no** (131%) | no (143%) | no (117%) | no (142%) |
| 2. VERIFY wrong = 0 | **no** (4) | yes | no (4) | yes |
| 3. VERIFY recall ≥ EXTRACT − 5 pts | yes | yes | yes | yes |
| 4. VERIFY qualifier errors ≤ EXTRACT | yes | yes | yes | yes |
No page type meets all four, mainly because of condition 1.

## Why VERIFY is not cheaper (observations; they do not change the decision)
- Per the frozen design, the VERIFY output schema carries the full set of final cells (confirmed, corrected and missed) plus one review entry per candidate.
  So VERIFY re-emits nearly everything EXTRACT does, plus the review, and it reads the candidates and page images either way.
- The image and page-text input dominates the cost, and both arms read the same inputs.
- Flash's candidates were sparse on two pages (Syros 2 rows, Victoris 17 rows, with 9 UNSURE in round 2), so VERIFY still had to find most cells itself.
- A VERIFY design that outputs only deltas against the candidates would cut output tokens, but it was not tested here. Testing it would be a new pre-registered design.

## Limits
- One page per type, 2 repeats: a pilot measurement, not a distribution. Cache read/creation counts vary between repeats.
- The text-layer "grid" page is a trims-as-row-headers list page, since no text-layer matrix page is in the gold set.
- Truth covers 19/32/16 cells per page, so the correctness figures say nothing about the 174 UNKNOWN cells.
- Default reasoning effort was left unchanged; thinking tokens are inside the output counts.

## Files
`PREREG_COSTCHECK.md`, `prompt_*.txt`, `build_inputs.py`, `score_costcheck.py`, `run_costcheck.sh`, `inputs_frozen/`, `results/` (runs, detail, unknown cells, metrics).
Scratch only: raw `out.json` per run, rendered tiles, input folders.
