# Blind check: CarWale EV range parser (P12), 22 Nov 2026

- **Classifier:** `kbpipe/sources/carwale.py` `_ev_range` (commit 8b1149a). Run over 1,757 cached CarWale versions, 207 of them electric (`parser_output_all.tsv`), it decides 119 RANGE, 87 NONE and 1 BLOCKED.
- **Sample:** stratified, seed 20261122: 40 RANGE, 25 NONE and the 1 BLOCKED, shuffled with opaque ids (`sample.tsv`). The key was kept separately (`key.tsv`).
- **Checker:** a fresh Opus agent. It read only `sample.tsv` and the raw cached pages, never the parser code or its labels. It fetched nothing. Its answers are in `answers.tsv`, with the JSON evidence for each.
- **Result:** RANGE 40/40, NONE 25/25, BLOCKED 1/1 (100% in every class; the bar is ≥95%). Every RANGE value matched exactly.
- **Checker's caveat:** CarWale labels the field "Expected Range". The owner accepted it as the claimed figure on 22 Nov (see `PLAN_EV_RANGE_FILL.md`). A value is written only where CarDekho agrees, through the two-site gate.
