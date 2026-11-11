# Prepared enrichment batches (not applied)
Batches extracted, validated and dry-run on a scratch copy of prod, but not applied because the P11 side-file question (NEEDS_YOU N8) blocks every write after 11A.
Apply in order with `write_phase.sh <phaseid> apply_enrich.py <PHASE> <batch>/cells.tsv` once N8 is answered; the script re-checks every old value against prod, so a stale batch fails safe.

| prepared | brochure / pages | cells | held | dry run |
|---|---|---|---|---|
| 11B Nexon | tata_nexon_brochure.pdf p38, p39, p40 (SHA-1 4485b424…) | 143 (15 changes, 14 quarantines released) | 28 (11 footnote, 15 page conflict, 2 absent) | clean, idempotent |
| 11C Seltos | kia_seltos_brochure.pdf p10 (SHA-1 c254b274…) | 160 (47 changes, 29 quarantines released) | 40 (HUD not shown) | clean, idempotent |

Tokens per page (gross, all token kinds), run A = every cell, run B = only the validated pairs:
| batch | pages | run A per page | run B per page |
|---|---|---|---|
| 11A Syros (B on every cell, old design) | 1 | 62,764 | 44,311 |
| 11B Nexon | 3 | 46,791 / 42,033 / 42,896 | 25,806 / 31,683 / 17,157 |
| 11C Seltos | 1 | 74,344 | 51,117 |
