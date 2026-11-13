# Phase 11Q — enrichment batch: cruise, wireless and fuel-tank cells checked against the brochure
Date: 2026-11-13. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `b174b0ac06a53bf190c557cb7c6f8b23e938cdd1` → `7c0de89b902e105492345db28366e526d29bc3b6` |
| Backup | `pre_phase11q_20261113T165941Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf` p10 11 12, SHA-1 `352bd5977f225145e35687450ee4635e0d7416aa` |

## Extraction [VERIFIED `classified.tsv`]
- 221 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 8 validated pairs (every correction plus the stratified fill sample): 8 of 8 agree (100.0%, gate 95%).
- Written 39 cells: FILL 8, CORRECTION 0, CONFIRM 31. Held 0 (none).
- Three pages: p10 and p11 (feature matrices, columns Era, Magna, Corporate, Sportz, Sportz VIBE, Sportz (O), Sportz (O) VIBE, Asta) and p12 (specification table, fuel tank 37 L).
- Two extraction runs failed on the first attempt (run A on p12 returned an empty result with zero tokens; run B on p11 never wrote output) and were re-run. Only the successful outputs are used.
- Only confirmations and explicit-dash fills: cruise control and wireless charger rows print S or a dash per trim, with "PL only" on Sportz cruise control. The CNG cylinder's 60 L water equivalent on p7 is not used.

## Write [VERIFIED `apply_prod_log.txt`]
39 cells: 8 filled, 0 corrected, 31 confirmed; 39 OEM observations and provenance rows; 8 amendments; 1 existing quarantines on these cells released; 0 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the page's trim columns (Era, Magna, Corporate, Sportz, Sportz (O), Asta and the VIBE columns) match the KB's Grand i10 Nios trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 27,891 / 64,560 / 20,083; run B per page 55,405.

## Not done / held
- Mileage, head-up display, ventilated seats, paddle shifters, drive modes: not on the pages read.
