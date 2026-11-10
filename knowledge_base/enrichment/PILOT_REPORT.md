# Flash extraction pilot (Claude Code ⇄ Gemini 3.8 Flash via agy): decision report
Date: 2026-11-10 · Branch `kb/enrich-flash` (from `kb/policy-20261106` @ fcbcbbe) · read-only on prod.

## DECISION: **ALL-CLAUDE** (arm 1, the specified instruction: precision 0% < 90%)
The sensitivity arm 2 (one clarifying sentence) reached 6/6 correct passing rows with a 22% pass rate.
That maps to HYBRID-LIMITED, but on n=6 (Wilson 95% lower bound ≈ 61%) and recall 2/40. It is not
evidence enough to delegate extraction. See §7.

## 0. Access [VERIFIED]
- `lsof +c 0` on `.db`/`-wal`/`-shm`: no holders, no `-wal`/`-shm` files. Prod SHA-1 `758310ea3ea1868dd94cebc9f9535b34719fd994`
  before the copy, after the copy, mid-run and at the end. The byte copy in `~/carrec_kb_scratch/enrich_flash/prod/` has the same SHA-1.
- All queries ran on `prod/q.db`, a second copy. No repo script was run against any DB.

## 1. Gemini bridge and isolation [VERIFIED]
- `ask_gemini.sh <prompt_file> [label]`: agy 1.5.5 headless, `env -u` for the 4 API/Vertex variables, cwd `agy_cwd/`,
  `--effort low --output-format json --print-timeout 300s`. Raw JSON goes to `calls/NNN.json`, and `conversation.log`
  gets timestamped CLAUDE→GEMINI (40-line truncation) and GEMINI→CLAUDE blocks. One retry on timeout (never needed).
  80-call cap, with every invocation counted. Stop check per call: billing/API-key wording in the output, or
  `authMethod=consumer` missing from agy's log → exit 42. `watch.sh` colours the log for the owner's pane.
- **Isolation uses supported features only; `~/.gemini` was not edited:**
  - `--agent extractor`: project agent `agy_cwd/.agents/agents/extractor.md` with `excludeDefaultComponents: true`,
    `tools: []`, `inheritMcp: false` (changelog: "opt out of default prompt sections and built-in tools").
  - `--settings '{"toolPermission":"strict","allowNonWorkspaceAccess":false,"enableTerminalSandbox":true}'`:
    session-only, never saved. agy validates the value (`bogus-mode` is rejected; agy logs `toolPermission=strict`).
  - `--sandbox`; never `--dangerously-skip-permissions`.
  - The 110 shared allow rules (38 valid `command(...)`) still load (`allow=110` in the log), but no tool exists to use them.
- **Canary (#001):** asked agy to list `~` and to read `agy_cwd/canary.txt` (a random token). Reply: "I cannot access files or
  list directories…". `denied_actions` was empty. The transcript has 2 steps (USER_INPUT, PLANNER_RESPONSE) and no tool step.
  The token is absent from the output. Input was **496 tokens**, against 8,365 for the default agent on a similar prompt
  (`~/agy-test/smoke1.out`), so the tool schemas were never sent.
- Every call used Google sign-in (`authMethod=consumer`). No billing, API-key or paid-plan wording appeared in any output.
  `useG1Credits=false`.
- Note: agy's own `--log-file` (`calls/NNN.agy.log`, scratch only, not committed) records the account email.

## 2. Brochure index [VERIFIED `index/index.tsv`]
`build_index.py` checks each PDF's SHA-1 against the KB-cited SHA-1 (a mismatch is skipped, and that path was exercised once).
It writes `p<N>.txt`, `p<N>.tables.json` and, for image-only (<50 chars) or scrambled (>45% one-char tokens) or rotated
(<80% upright) pages, Vision OCR `p<N>.ocr.txt`, rebuilt into rows by y-position. Renders go to scratch only.
- 5 brochures, 63 pages: **text 41 · ocr 12 · text+ocr 10**. About 28 s of page work: 0.05 s/page for text,
  about 1.0–1.4 s/page with OCR.
- Full library: 67 PDFs, 1,289 pages. At this mix (~35% OCR), expect about **10–20 min** for a full index.

## 3. Gold set [VERIFIED `gold.tsv`, `make_gold.py`]
40 cells from brochure-cited OEM observations (`manual_brochure_10E/10J/10K/10N`, payload has pdf path, page and SHA-1),
each equal to the current `v_variant_canonical_q` value (asserted).

| Brochure | page | prompt input | cells |
|---|---|---|---|
| Ertiga | 7 | OCR (image-only) | 7 (km/l 5, km/kg 2) |
| Victoris | 16 | OCR (scrambled layer) | 11 (km/l 4, km/kg 1, cruise 4, paddle 2) |
| Dzire | 5 | OCR (scrambled layer) | 4 (km/l 3, km/kg 1) |
| Kia Syros | 7 | text | 8 (cruise 5, wireless 3) |
| Tata Altroz | 22 | text | 10 (cruise 5, wireless 5) |

Fields: km/l 12, CNG km/kg 4, cruise 14, wireless 8, paddle 2; 22 OCR-input, 18 text; values 1 and 0 both included.
Gemini saw only page text, the instruction and the model's variant names, never gold.tsv or any KB value.

## 4. Pilot
- One call per gold page. The prompt (`make_prompts.py`) had the exact instruction from the brief, one line of field
  meaning (value 1/0 convention, unit), variant names, "JSON array only", then the page text: pdfplumber tables first,
  then the text layer (text pages) or the OCR (ocr / text+ocr pages).
- **Arm 2 (sensitivity, not in the brief):** identical prompt plus one sentence: "printed_label means the variant,
  trim and/or gearbox label printed on the page that the value applies to …; it is never the feature or
  specification name." I added it after arm 1 showed every label was a feature name.
- Filter and scoring: `filter_score.py`, deterministic, no LLM. Rules (a)/(b)/(c) and the label→variant mapping are
  documented in its docstring. Notes on the rules:
  - (b) for yes/no fields needs a keyword or presence mark for 1, and an absence mark for 0.
  - An "in addition to <trim>" back-reference is stripped before trim matching.
  - A label that contains a feature word (cruise, wireless, efficiency, …) maps to NONE.
  - Precision counts a passing row correct only if its label maps to variant(s) (trim-level or model-level such as
    "MT"/"AT") and the value equals the brochure truth for every mapped variant that has a truth value. Truth is all
    192 brochure-verified 10E–10N OEM cells (5 fields, all brochures; the gold pages’ cells are used).
  - Rows with labels that name no variant are **UNATTRIBUTABLE** (not correct: they cannot be written).
  - One row needed a manual page reading (`manual_judgements.tsv`, 010.2).

## 5. Results [VERIFIED `score_arm1/`, `score_arm2/`]
| | arm 1 (as specified) | arm 2 (+1 sentence) |
|---|---|---|
| rows / passing | 25 / 16 | 27 / 6 |
| **pass rate** | **64%** | 22% |
| **precision** | **0% (0/16)**, all 16 UNATTRIBUTABLE | **100% (6/6)** |
| **recall (trim-level FOUND)** | **0/40** | 2/40 |
| recall text / OCR pages | 0/18 · 0/22 | 2/18 · 0/22 |
| also found only via model-level label ("MT", "AT") | 0 | 4 |
| quotes: exact / relabelled / invented | 21 / 4 / 0 | 23 / 4 / 0 |
| wrong values (number not on page, or wrong for the mapped label among passing rows) | 0 | 0 |
| UNSURE labels | 0 | 1 |
| reject reasons | c fails 5, a+c fail 4 | c fails 17, a fails 4 |

- **Arm 1:** Flash put the feature name in `printed_label` ("Cruise control ***", "Fuel Efficiency", "Drive with a
  mileage of:"). Every value was real, but no row ties a value to a variant.
- **Arm 2:** labels became trims ("VXi AT, ZXi AT, ZXi+ AT", "Zxi+ / Zxi+ (O)", "HTK+ [Features in addition to HTK(EX)]").
  Rule (c), "label in the quote or table header", then rejects most of them, because on matrix or OCR pages the
  label sits in a column header away from the value. Diagnostic: of the 21 rejected arm-2 rows, **11 were correct** for
  their label and 4 wrong. The wrong ones:
  - Victoris paddle "Zxi / Zxi (O)" = 1, where the page says 6AT only, so the label wrongly covers MT;
  - an OCR typo "ALLORP" that hides ALLGRIP;
  - a Dzire label covering MT and AMT for the AMT figure.
  So the filter blocks real errors, but at a large recall cost.
- **Relabelled quotes (4 per arm)** all come from the Victoris OCR mileage block. Flash rebuilt the quote across lines
  ("21.18\nkm/l\nPetrol (MT"), and the joined text is not contiguous on the page. **Invented quotes: 0.** The earlier
  ~/agy-test run had 1 invented quote of 7.
- Timing: 10 extraction calls, **14.4 s wall** each on average (agy-reported 4.8 s). 41,210 input / 3,218 output tokens,
  0 thinking tokens at `--effort low`. No timeouts.
- Calls used: **12 / 80**: #001 canary; #002 an empty-prompt failure (a wrapper bug with relative paths, fixed; agy
  exited before sign-in and the stop check fired, correctly); #003–007 arm 1; #008–012 arm 2.

## 6. Blind check of the scoring [VERIFIED `blind_agreement.tsv`]
A fresh general-purpose subagent saw only `blind/` (RULES.md in prose, the page text, variant names and 25 rows with
opaque ids). It never saw the code, my labels, the gold set or KB values. Sample: 15 random passing + 10 random rejected rows
from both arms (seed 20261110).
- **Agreement 24/25 = 96% (≥95%, continue).** Per check: a 25/25, b 25/25, c 24/25.
- Disagreement: B17 = row 006.8, with the label "Paddle Shifters" and a merged row header "Keyless Entry Paddle Shifters".
  My code tests header *containment*; the blind reader took "is the row header" as equality. It changes status, not
  precision (the verdict is UNATTRIBUTABLE either way). If the rule is kept, tighten it to equality.
- Interpretation points the blind reader flagged: table header row = first line, even when it is a section title
  ("FEATURE SPECIFICATIONS"); a yes/no "value in the cell" was read as the feature text in the cell. Both follow the rules as
  written and would only move rows from REJECTED to WRONG, not to CORRECT.
- Limits: the subagent inherits the project CLAUDE.md (no values for these cells). The sample covers 25 of 52 rows.

## 7. Decision table
- Arm 1 (the specified prompt): precision 0% < 90% → **ALL-CLAUDE**.
- Arm 2, for information: 100% ≥ 95% with pass rate 22% < 50% → would be HYBRID-LIMITED. But 6 rows across 4 pages is too
  small: 1 error would put it at 83%, and recall on OCR pages is 0/22. Re-running this with a larger page sample and a
  table-aware (c) is the obvious next pilot, not a decision.
- Why recall is near zero even in arm 2: the label is in a column header or in a cumulative "in addition to" list, which
  rule (c) cannot see on OCR pages (no tables) and which needs inheritance across trims. That is the work Claude did by
  hand in 10N.

## 8. Side finding (read-only; nothing written)
Kia Syros p7 text layer: the HTX block "[Features in addition to HTK+ (O)]" lists "Smartphone Wireless Charger", outside
"Automatic Only Features". The KB has **764 HTX Diesel Automatic wireless_charging = 0** (v6_migration, and a v3cars "confirmation"
with an empty feature list), while 763 HTX Petrol DCT = 1. It is a backlog candidate: render and visually confirm p7 (P1) before any write.

## Files
Committed in `knowledge_base/enrichment/`:
- code: `ask_gemini.sh`, `watch.sh`, `ocr.swift`, `build_index.py`, `make_gold.py`, `make_prompts.py`, `filter_score.py`, `compare_blind.py`
- the agent definition, under `agy_agent/extractor.md`
- `results/`: gold.tsv, both arms' rows, recall and metrics, `manual_judgements.tsv`, `blind_agreement.tsv`, `calls_index.tsv`

Scratch only (`~/carrec_kb_scratch/enrich_flash/`), not committed:
- raw call JSON, agy logs and prompts (they contain brochure text and, in agy logs, the account email)
- the index and the DB copies
