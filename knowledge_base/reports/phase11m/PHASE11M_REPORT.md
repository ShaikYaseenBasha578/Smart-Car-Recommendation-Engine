# Phase 11M — enrichment batch: feature, fuel-tank and drive-mode cells checked against the brochure
Date: 2026-11-12. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `52711fd11c87df56670f6970b7f733824d3455b8` → `8039119ba0ba5e787025d198e1f2aad569c19c3a` |
| Backup | `pre_phase11m_20261112T151417Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `hyundai/venue/latest/brochures/hyundai_venue_brochure.pdf` p18 19 20, SHA-1 `00eabf1c73ad06d076b7e3928d9ca54d9b4cb1c4` |

## Extraction [VERIFIED `classified.tsv`]
- 323 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 11 validated pairs (every correction plus the stratified fill sample): 11 of 11 agree (100.0%, gate 95%).
- Written 97 cells: FILL 13, CORRECTION 1, CONFIRM 83. Held 0 (none).
- Three pages: p18 (specification table, fuel tank 45 L), p19 and p20 (feature matrices with S or dash per trim: HX 2 to HX 10 and the Knight editions' columns).
- One correction, backed by an explicit dash: front-row ventilated seats yes → no on HX 7 Diesel MT. Drive modes are written from the "Drive mode select (Eco, Normal, Sport)" row only: S = 3, an explicit dash = 0; the "^" DCT/AT restriction is applied by gearbox.
- Earlier phases (10E-10N) had already brochure-verified 16 Venue cells; they are not rewritten.

## Write [VERIFIED `apply_prod_log.txt`]
97 cells: 13 filled, 1 corrected, 83 confirmed; 97 OEM observations and provenance rows; 14 amendments; 0 existing quarantines on these cells released; 3 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the page columns (HX 2, HX 4, HX 5, HX 5+, HX 6, HX 6T, HX 7, HX 8, HX 10 and the Knight editions) match the KB's Venue trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 20,784 / 53,891 / 59,186; run B per page 66,922.

## Not done / held
- Mileage and head-up display: not on the pages read.
