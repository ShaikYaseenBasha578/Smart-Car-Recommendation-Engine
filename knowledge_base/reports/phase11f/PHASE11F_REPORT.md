# Phase 11F — enrichment batch: feature, fuel tank and drive-mode cells checked against the brochure
Date: 2026-11-12. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `96356815f547d153183c37958f3e92d1ad6bdbf0` → `58d3ef0ef0ea641e852e1438cc023378b8ae0822` |
| Backup | `pre_phase11f_20261112T145407Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `mahindra/xuv_7xo/latest/brochures/mahindra_xuv_7xo_brochure.pdf` p28 30, SHA-1 `2f29e135087305a1edac4abc013062969892540f` |

## Extraction [VERIFIED `classified.tsv`]
- 432 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 11 validated pairs (every correction plus the stratified fill sample): 11 of 11 agree (100.0%, gate 95%).
- Written 124 cells: FILL 16, CORRECTION 1, CONFIRM 107. Held 0 (none).
- Two image-only pages read through OCR plus rendered tiles: p28 (variant walk, cumulative lists AX to AX7 LUXURY) and p30 (specification table, fuel tank 60 L).
- Cruise control comes from the AX list and the cumulative tiers, with the AX7 TECH adaptive cruise (AT only); wireless charging only from the AX7 TECH / AX7 LUXURY lines (zeros are tier evidence: the feature is listed at higher tiers); drive modes only from "Zip, Zap, Zoom & Custom Mode (Diesel Only)" (4 modes, diesel variants); petrol variants are unknown.

## Write [VERIFIED `apply_prod_log.txt`]
124 cells: 16 filled, 1 corrected, 107 confirmed; 124 OEM observations and provenance rows; 17 amendments; 0 existing quarantines on these cells released; 17 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the page's variant columns (AX, AX3, AX5, AX7, AX7 TECH, AX7 LUXURY) match the KB's XUV 7XO trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 53,308 / 64,533; run B per page 34,295.

## Not done / held
- Mileage, head-up display and paddle shifters: not shown on the pages read.
- Drive modes on petrol variants: the row says diesel only, so unknown.
