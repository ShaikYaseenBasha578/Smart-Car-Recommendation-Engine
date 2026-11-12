# Phase 11K — enrichment batch: feature, mileage, fuel-tank and drive-mode cells checked against the brochure
Date: 2026-11-12. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `ff444f4a23d6d2f12cd980fac5e123bd8d335c9f` → `289240826f50c972373f5b9f70138f895c42df06` |
| Backup | `pre_phase11k_20261112T150746Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `maruti_suzuki/grand_vitara/latest/brochures/maruti_suzuki_grand_vitara_brochure.pdf` p15, SHA-1 `023ce2e3d22ca4bd3a2cd1a9aded193273482e91` |

## Extraction [VERIFIED `classified.tsv`]
- 152 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 14 validated pairs (every correction plus the stratified fill sample): 14 of 14 agree (100.0%, gate 95%).
- Written 134 cells: FILL 5, CORRECTION 9, CONFIRM 120. Held 0 (none).
- One page: p15, a true feature and specification matrix with explicit tick or dash markers per trim column (Sigma, Delta, Zeta/Zeta(O), Alpha/Alpha(O)/Alpha ALLGRIP(O), Delta+, Zeta+/Zeta+(O), Alpha+/Alpha+(O)) over petrol MT/AT/AllGrip, CNG and strong hybrid variants.
- 9 corrections, all backed by an explicit dash or figure: ventilated front seats yes → no on Zeta, Zeta(O) and Zeta+ (7 cells), wireless charging yes → no on Delta+ strong hybrid, and Alpha(O) AllGrip AT km/l 20.58 → 19.20 (printed "19.20 (ALLGRIP AT)").
- The brochure prints no CNG data, so km/kg on CNG variants (548/549 unverified since 10F) is unchanged.

## Write [VERIFIED `apply_prod_log.txt`]
134 cells: 5 filled, 9 corrected, 120 confirmed; 134 OEM observations and provenance rows; 14 amendments; 0 existing quarantines on these cells released; 14 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the page's trim columns match the KB's Grand Vitara trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 83,643; run B per page 68,634.

## Not done / held
- CNG km/kg: the Grand Vitara brochure has no CNG data (still unverified).
- Pass over any further pages (fuel tank 45 L was confirmed from the matrix).
