# Phase 11E — enrichment batch: feature, fuel tank and drive-mode cells checked against the brochure
Date: 2026-11-12. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `b653b3f8d6858fe9080ecfe32c5883b6ec99ce3c` → `96356815f547d153183c37958f3e92d1ad6bdbf0` |
| Backup | `pre_phase11e_20261112T145121Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `mahindra/scorpio_n/latest/brochures/mahindra_scorpio_n_brochure.pdf` p23 24, SHA-1 `92389b0b114018b5886c237e6c2e2cb70f58c97e` |

## Extraction [VERIFIED `classified.tsv`]
- 270 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 22 validated pairs (every correction plus the stratified fill sample): 22 of 22 agree (100.0%, gate 95%).
- Written 125 cells: FILL 71, CORRECTION 6, CONFIRM 48. Held 0 (none).
- Two pages: p23 (specification table, fuel tank 57 L) and p24 (feature matrix, Z2 to Z8L columns by petrol/diesel). Ticks are images, so the rendered tiles are the authority.
- Cruise control rests on the "Steering Remote Controls" row (Audio vs Audio + Cruise) and the adaptive cruise row (AT variant only); wireless charging on the "Wireless Charger (With Active Cooling)" row, not wireless Android Auto; drive modes only from the "Drive Modes (Diesel) - Zip-Zap-Zoom" row (a tick = 3 modes, an explicit x = 0); petrol variants are not on that row and stay unknown.

## Write [VERIFIED `apply_prod_log.txt`]
125 cells: 71 filled, 6 corrected, 48 confirmed; 125 OEM observations and provenance rows; 77 amendments; 0 existing quarantines on these cells released; 6 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the page columns (Z2, Z4, Z6, Z8S, Z8, Z8T, Z8L by petrol/diesel) match the KB's Scorpio-N trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 38,724 / 61,496; run B per page 40,958.

## Not done / held
- Mileage: the pages read print no km/l.
- Head-up display and paddle shifters: not shown on the pages (unknown, not zero).
- Drive modes on petrol variants and Diesel 4WD: not on the page row.
