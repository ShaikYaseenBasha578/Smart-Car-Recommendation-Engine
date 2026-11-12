# Phase 11H — enrichment batch: feature, fuel tank and drive-mode cells checked against the brochure
Date: 2026-11-12. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `e351341cf8eaffb8164651fc7ed61f09d74a51fa` → `98a46dbdb7e133f712c9df8072049cc89377bacb` |
| Backup | `pre_phase11h_20261112T145900Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `tata/altroz/latest/brochures/tata_altroz_brochure.pdf` p22 23, SHA-1 `5cbbf8b65224b23bb027ff078fe5e4721f793d25` |

## Extraction [VERIFIED `classified.tsv`]
- 135 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 37 validated pairs (every correction plus the stratified fill sample): 37 of 37 agree (100.0%, gate 95%).
- Written 74 cells: FILL 38, CORRECTION 27, CONFIRM 9. Held 0 (none).
- Two pages: p22 (persona list Smart to Accomplished+ S with footnote legend: ** Petrol DCA only, # Petrol MT, AMT and Diesel MT only, *** Petrol MT, AMT, DCA, CNG MT and Diesel only) and p23 (specification table: fuel tank 37 L petrol and diesel; CNG water capacity 60 L).
- The 27 fuel-tank corrections: the KB held 60 L on every Altroz variant (the CNG cylinder water capacity) and the brochure prints 37 L as the petrol/diesel tank, which is also the petrol tank used for CNG variants (glossary rule, as for Dzire and Victoris CNG). Run B agreed on all 27.
- Footnote markers here are item-specific (**, #, ***) and tie each item to its legend line, unlike the Nexon page's single starred disclaimer, so printed restrictions are applied (paddle shifters Petrol DCA only: manual/AMT variants 0, DCA variants 1; drive modes 2 for the variants named by #, others unknown).

## Write [VERIFIED `apply_prod_log.txt`]
74 cells: 38 filled, 27 corrected, 9 confirmed; 74 OEM observations and provenance rows; 65 amendments; 0 existing quarantines on these cells released; 27 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the persona columns (Smart, Pure, Pure S, Creative, Creative S, Accomplished S, Accomplished+ S) match the KB's Altroz trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 29,887 / 22,699; run B per page 34,915 / 21,826.

## Not done / held
- Mileage and head-up display: not on the pages read.
- Drive modes on DCA and CNG variants: the row names other variants only.
