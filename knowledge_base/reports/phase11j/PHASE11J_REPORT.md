# Phase 11J — enrichment batch: feature and fuel-tank cells checked against the brochure
Date: 2026-11-12. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `39f913e6f93d301ed7e1a84100ff78c2d1713947` → `ff444f4a23d6d2f12cd980fac5e123bd8d335c9f` |
| Backup | `pre_phase11j_20261112T150346Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `tata/tiago/latest/brochures/tata_tiago_brochure.pdf` p27 28, SHA-1 `245f8902fb90cb3f50f576ec63a09e7ee6bc774f` |

## Extraction [VERIFIED `classified.tsv`]
- 180 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 36 validated pairs (every correction plus the stratified fill sample): 36 of 36 agree (100.0%, gate 95%).
- Written 77 cells: FILL 17, CORRECTION 26, CONFIRM 34. Held 1 (1 FOOTNOTE_REVIEW).
- Two pages: p27 (specification table: fuel tank 35 L for petrol and the iCNG petrol tank, CNG cylinder 60 L water capacity) and p28 (persona list Smart to Creative+, cumulative "in addition to" lines).
- The 20 fuel-tank corrections: the KB held 60 L (the CNG water capacity) on every Tiago variant; the brochure's petrol tank is 35 L, which is also used for the iCNG variants (same rule as Altroz 11H). Run B agreed on all 20.
- One zero (cruise control on a CNG AMT variant, resting on the "*Cruise control is not available in CNG AMT" footnote) is held by the footnote guard.

## Write [VERIFIED `apply_prod_log.txt`]
77 cells: 17 filled, 26 corrected, 34 confirmed; 77 OEM observations and provenance rows; 43 amendments; 6 existing quarantines on these cells released; 26 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the persona columns (Smart, Pure, Pure+, Pure+ A, Creative, Creative+) match the KB's Tiago trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 20,883 / 105,845; run B per page 49,559 / 32,770.

## Not done / held
- Mileage, head-up display and drive modes: not on the pages read (drive modes were not listed).
- One CNG AMT cruise-control zero held by the footnote guard.
