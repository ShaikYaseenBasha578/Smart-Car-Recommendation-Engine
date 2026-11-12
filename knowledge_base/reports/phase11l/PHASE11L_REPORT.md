# Phase 11L — enrichment batch: feature, fuel-tank and drive-mode cells checked against the brochure
Date: 2026-11-12. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `289240826f50c972373f5b9f70138f895c42df06` → `52711fd11c87df56670f6970b7f733824d3455b8` |
| Backup | `pre_phase11l_20261112T151105Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `mahindra/thar_roxx/latest/brochures/Thar_Roxx_Brochure.pdf` p1 2 3, SHA-1 `1c4e667fee5459888bf9ed3def8edcda9fdfdaf7` |

## Extraction [VERIFIED `classified.tsv`]
- 432 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 17 validated pairs (every correction plus the stratified fill sample): 17 of 17 agree (100.0%, gate 95%).
- Written 86 cells: FILL 14, CORRECTION 7, CONFIRM 65. Held 0 (none).
- Three image-only pages (p1 variants and specifications, p2 comfort and connectivity, p3 safety and drivetrain), read through OCR and rendered tiles. Columns MX1, MX3, AX3L, MX5, AX5L, STAR EDN, AX7L over petrol and diesel 2WD/4x4 MT/AT.
- 7 corrections, each with an explicit x or tick in the cell: wireless charging yes → no on MX3, MX5 and AX3L (6 cells) and cruise control no → yes on MX3 Diesel AT. Drive modes (Zip & Zoom = 2 modes) are written only where the cell is ticked for RWD; 4x4 variants stay unknown.
- The "STAR EDN" column is the Star Edition; the KB's Thar Roxx variants are all base variants and are matched by name.

## Write [VERIFIED `apply_prod_log.txt`]
86 cells: 14 filled, 7 corrected, 65 confirmed; 86 OEM observations and provenance rows; 21 amendments; 7 existing quarantines on these cells released; 17 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the page columns (MX1, MX3, AX3L, MX5, AX5L, Star Edition, AX7L) match the KB's Thar Roxx trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 62,162 / 50,555 / 51,243; run B per page 46,703 / 36,583.

## Not done / held
- Mileage, head-up display and paddle shifters: not on the pages read.
- Drive modes on 4x4 variants: the tick is printed for RWD only.
