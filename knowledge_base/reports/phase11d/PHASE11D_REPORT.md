# Phase 11D — enrichment batch 4: Hyundai Creta (feature cells, drive modes)
Date: 2026-11-12. Fourth batch of the Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change. (11C Seltos was held under P7 by owner decision; Carens Clavis was rejected at the gate, see below.)

| | |
|---|---|
| Prod before / after | `afad3a5fecefa98335cdb1db91c9f4528b8aab55` → `b653b3f8d6858fe9080ecfe32c5883b6ec99ce3c` |
| Backup | `pre_phase11d_20261112T144558Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf` p13, p14, SHA-1 `cc5b2fbc3490e16d1e5de56d61b49eb7372ce362` (PDF created 2026-08-17) |

## Extraction [VERIFIED `classified.tsv`]
- Two feature-matrix pages (p13 safety/ADAS rows, p14 comfort rows), 31 base variants, 8 fields, 496 cells. Run A read every cell. Run B (blind, own folder, no run-A output) answered only the 24 validated pairs (14 corrections + 10 sampled fills): 24 of 24 agree.
- Classes: FILL 10 (all drive modes), CONFIRM 124 (114 written; 10 fills + 14 corrections written = 138 cells), CORRECTION 14, NOT_ON_PAGE 343, already verified 5.
- First pass found 28 cross-page conflicts on cruise control: p13 printed only a "Smart Cruise Control with Stop & Go" row (dash on S(O)/SX), and run A turned that dash into 0 while p14's plain "Cruise control" row says S. The glossary now says a dash in an adaptive-cruise row alone is NOT_ON_PAGE, and the pages were re-extracted: 0 conflicts. Only the second extraction is used.
- Drive modes: written only from an explicit row ("Drive mode select (Eco, Normal, Sport)", S/S* or dash). The "*" (iVT/AT) restriction is applied by gearbox.

## Write [VERIFIED `apply_prod_log.txt`]
138 cells: 10 filled, 14 corrected, 114 confirmed; 138 OEM observations and provenance rows; 24 amendments; 31 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the brochure's columns (E, EX, EX(O), S(O), S(O) Knight, SX, SX Premium, King, King Knight) are exactly the KB's Creta trims; the PDF is dated 2026-08-17 · P8 base variants only (Creta has no editions in the KB) · P9 n/a · P13 not triggered.

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 85,503 (p13) and 65,109 (p14); run B 43,096 (p14, 24 pairs). The first, discarded pass cost 48,133 + 64,447 for A.

## Not done / held
Mileage, fuel tank and paddle shifters on the remaining trims are NOT_ON_PAGE (the Creta brochure prints no km/l; fuel tank is on a page not yet read). 
