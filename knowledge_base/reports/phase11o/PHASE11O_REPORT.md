# Phase 11O — enrichment batch: mileage, feature and fuel-tank cells checked against the brochure
Date: 2026-11-13. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `cd7bc92056b71d18831fd9b3eb7ba96461ea80c5` → `2efefc4f30505f2d7961a77204b8d83f8d6a6b48` |
| Backup | `pre_phase11o_20261112T193958Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf` p6 7, SHA-1 `951f428bf95ccd0f9e94eb24a62d87aaf382dd5a` |

## Extraction [VERIFIED `classified.tsv`]
- 84 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 14 validated pairs (every correction plus the stratified fill sample): 14 of 14 agree (100.0%, gate 95%).
- Written 56 cells: FILL 0, CORRECTION 14, CONFIRM 42. Held 0 (none).
- Two pages: p6 (variant and specification table: trims LXi, VXi, VXi(O), ZXi, ZXi+ and CNG, fuel tank "Petrol: 37; CNG: 55 (Water Filling Capacity)", cruise control and wireless charger rows) and p7 (ARAI fuel efficiency 24.80 km/l MT, 25.75 km/l AMT, 32.85 km/kg CNG).
- The 14 fuel-tank corrections: the KB held 55 L (the CNG water capacity) on every Swift variant; the brochure's petrol tank is 37 L, also used for the CNG variants (glossary: the CNG cylinder's water capacity never goes in this field). Run B agreed on all 14.
- Everything else is confirmation: cruise, wireless and the three mileage figures already matched the brochure.

## Write [VERIFIED `apply_prod_log.txt`]
56 cells: 0 filled, 14 corrected, 42 confirmed; 56 OEM observations and provenance rows; 14 amendments; 0 existing quarantines on these cells released; 14 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the brochure is the Gen4 2024 one (PDF dated 2024-11-20); its trims (LXi, VXi, VXi(O), ZXi, ZXi+, CNG) match the KB's Swift variants one to one, and nothing date-sensitive is changed (only confirmations and the water-capacity fix) · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 59,035 / 35,009; run B per page 22,317.

## Not done / held
- Head-up display, ventilated seats, paddle shifters, drive modes: not on the pages read.
