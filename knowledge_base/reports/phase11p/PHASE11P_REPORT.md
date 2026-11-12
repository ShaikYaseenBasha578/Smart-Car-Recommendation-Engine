# Phase 11P — enrichment batch: cruise-control and fuel-tank cells checked against the brochure
Date: 2026-11-13. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `2efefc4f30505f2d7961a77204b8d83f8d6a6b48` → `b174b0ac06a53bf190c557cb7c6f8b23e938cdd1` |
| Backup | `pre_phase11p_20261112T194131Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `tata/tigor/latest/brochures/tata_tigor_brochure.pdf` p18 19, SHA-1 `1867cdf175b0ea07d327c5874117e36f32f5308e` |

## Extraction [VERIFIED `classified.tsv`]
- 126 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 16 validated pairs (every correction plus the stratified fill sample): 16 of 16 agree (100.0%, gate 95%).
- Written 22 cells: FILL 7, CORRECTION 9, CONFIRM 6. Held 0 (none).
- Two pages: p18 (persona list XM to XZ+ Lux, cumulative "features over") and p19 (specification table: fuel tank 35 L petrol; 70 L is the iCNG water capacity).
- The 8 fuel-tank corrections: the KB held 60 L (a CNG water capacity) on the petrol variants; the brochure prints 35 L. iCNG variants were not on the 35 L cell and stay untouched.
- Cruise control: listed first at XZ+ with the printed restriction "(petrol only)", so the CNG variants and lower trims are 0 (printed restriction, or tier evidence); one correction no → yes on XZ+.

## Write [VERIFIED `apply_prod_log.txt`]
22 cells: 7 filled, 9 corrected, 6 confirmed; 22 OEM observations and provenance rows; 16 amendments; 1 existing quarantines on these cells released; 9 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the persona columns (XM, XT, XZ, XZ+, XZ+ Lux) match the KB's Tigor trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 32,708 / 42,073; run B per page 30,650 / 20,053.

## Not done / held
- Mileage, wireless charging, head-up display, ventilated seats, paddle shifters, drive modes: not on the pages read.
- iCNG fuel tank: the page prints 35 L and a 70 L water capacity in one column; left unknown.
