# Phase 11G — enrichment batch: cruise, wireless and fuel-tank cells checked against the brochure
Date: 2026-11-12. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `58d3ef0ef0ea641e852e1438cc023378b8ae0822` → `e351341cf8eaffb8164651fc7ed61f09d74a51fa` |
| Backup | `pre_phase11g_20261112T145615Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `mahindra/xuv_3xo/latest/brochures/mahindra_xuv_3xo_brochure.pdf` p13 14, SHA-1 `73015a758e9bba7e3961bcdea749b62603d682e5` |

## Extraction [VERIFIED `classified.tsv`]
- 78 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 15 validated pairs (every correction plus the stratified fill sample): 15 of 15 agree (100.0%, gate 95%).
- Written 56 cells: FILL 0, CORRECTION 1, CONFIRM 55. Held 14 (14 TIER_ABSENCE_CORRECTION).
- Two pages: p13 (Adrenox feature walk, cumulative "adds to" lists from MX1 to AX7 LUXURY) and p14 (specification table, fuel tank 42 L). Fields read per page: cruise control and wireless charging on p13, fuel tank on p14.
- Guard added during this batch: 14 corrections turning wireless charging from 1 to 0 on MX3, AX5 and AX7 rest only on "the charger is listed only under AX5 LUXURY". I read the page: the AX7 list "adds to AX5" and re-lists other AX5 LUXURY items (cooled glove box, Dolby Atmos) but neither AX7 list shows the charger, so the lists are not exhaustive about inheritance and not-listed is not evidence of absence. A stored 1 is now never flipped to 0 from tier absence alone (an explicit marker or printed restriction is needed). The 14 cells are held.
- Limit: confirmed zeros (cruise on MX1/MX2, wireless on lower trims) rest on the same tier structure; they confirm the stored value, they do not change it.

## Write [VERIFIED `apply_prod_log.txt`]
56 cells: 0 filled, 1 corrected, 55 confirmed; 56 OEM observations and provenance rows; 1 amendments; 2 existing quarantines on these cells released; 1 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the page's columns (MX1, MX2, MX3, MX2 PRO, MX3 PRO, AX5, AX7, AX5 LUXURY, AX7 LUXURY) match the KB's XUV 3XO trims (the KB also has REVX M, REVX M (O) and REVX A, which these pages don't cover and which are untouched) · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 40,515 / 22,103; run B per page 33,389.

## Not done / held
- Wireless charging on MX3, MX3 Pro, AX5 and AX7 (14 cells, stored yes): held, the brochure's lists are not exhaustive (see above).
- Mileage, head-up display, ventilated seats, paddle shifters, drive modes: not on the pages read.
