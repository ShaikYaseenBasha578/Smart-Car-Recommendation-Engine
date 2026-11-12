# Phase 11I — enrichment batch: feature, fuel tank and drive-mode cells checked against the brochure
Date: 2026-11-12. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `98a46dbdb7e133f712c9df8072049cc89377bacb` → `39f913e6f93d301ed7e1a84100ff78c2d1713947` |
| Backup | `pre_phase11i_20261112T150106Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `tata/harrier/latest/brochures/tata_harrier_brochure.pdf` p18 19 20, SHA-1 `93f7bf425f168db0f7a2a4b65b981ad21c7dd135` |

## Extraction [VERIFIED `classified.tsv`]
- 192 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 10 validated pairs (every correction plus the stratified fill sample): 10 of 10 agree (100.0%, gate 95%).
- Written 85 cells: FILL 14, CORRECTION 0, CONFIRM 71. Held 0 (none).
- Three pages: p18 and p19 (persona lists Smart to Fearless Ultra, cumulative "features over" lines) and p20 (specification table, fuel tank 50 L).
- Only base variants are written; the KB's two Harrier editions (Dark) inherit from their base and are untouched (P8).
- No correction in this batch: every value either filled a blank or confirmed a stored one.

## Write [VERIFIED `apply_prod_log.txt`]
85 cells: 14 filled, 0 corrected, 71 confirmed; 85 OEM observations and provenance rows; 14 amendments; 0 existing quarantines on these cells released; 3 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the persona columns (Smart, Pure X, Adventure X, Adventure X+, Fearless X, Fearless X+, Fearless Ultra) match the KB's Harrier trims (the Dark editions are editions) · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 39,152 / 40,227 / 38,327; run B per page 31,554.

## Not done / held
- Mileage and head-up display: not on the pages read.
- The two Dark editions: editions inherit from their base (P8).
