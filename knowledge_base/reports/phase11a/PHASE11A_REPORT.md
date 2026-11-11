# Phase 11A — enrichment batch 1: Kia Syros (feature cells)
Date: 2026-11-11. First batch of the Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `758310ea3ea1868dd94cebc9f9535b34719fd994` → `795a12233ee84147990f00e36816bfe841beb281` |
| Backup | `pre_phase11a_20261111T121749Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `a7ee03ef…`) |
| Source | `kia/syros/latest/brochures/kia_syros_brochure.pdf` p7, SHA-1 `7622f531b207ff69ab9ae6e3844653594356dced` |

## Extraction [VERIFIED `classified.tsv`]
- One page (p7), 17 base variants, 6 fields = 102 cells. Two independent headless Sonnet runs (Read-only, own folder, 3 tiles at 140 dpi plus the page text). They agreed on 102 of 102 cells.
- Classes: FILL 8, CONFIRM 40, CORRECTION 1, NOT_ON_PAGE 17 (all km/l: the brochure prints none), ABSENT_NOT_SHOWN 17 (all HUD), already brochure-verified 19.
- Absent-as-zero guard: both runs gave HUD = 0 because "the list has no HUD", but HUD appears nowhere on the page. That repeats the 10B absent-as-zero defect, so a 0 now needs an explicit absence marker, a printed restriction, or the feature shown fitted on another trim of the same page (`GLOSSARY.md`, `enrich_batch.py`). The 17 HUD cells are not written.
- Validation sample: the correction plus all 8 fills = 9 of 9 agree. I also read tile 2 myself: HTX lists "Smartphone Wireless Charger".

## Write [VERIFIED `apply_prod_log.txt`]
49 cells: 8 filled, 1 corrected, 40 confirmed; 49 OEM observations and provenance rows; 9 amendments; 2 contradicted provenance rows on 764 wireless charging quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (SHA checked against the file by the script) · P7 page columns match the KB trims · P8 Syros has no editions · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage.tsv`]
Run A 62,764 (output 10,498); run B 44,311 (output 9,429); total 107,075 for one page. From batch 2 run B covers only the validated pairs.

## Not done / held
17 km/l cells (no figure in the brochure, P9) and 17 HUD cells (not shown on the page).
