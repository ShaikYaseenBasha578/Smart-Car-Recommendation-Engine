# Phase 11N — enrichment batch: feature and fuel-tank cells checked against the brochure; N4 checked
Date: 2026-11-13. Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `8039119ba0ba5e787025d198e1f2aad569c19c3a` → `cd7bc92056b71d18831fd9b3eb7ba96461ea80c5` |
| Backup | `pre_phase11n_20261112T193541Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `hyundai/exter/latest/brochures/hyundai_exter_brochure.pdf` p10 11 12, SHA-1 `19da8e83686ae02be56cf6200d604906bc2b3779` |

## Extraction [VERIFIED `classified.tsv`]
- 375 cells read by run A. Run B (blind, own folder, no run-A output) answered only the 10 validated pairs (every correction plus the stratified fill sample): 10 of 10 agree (100.0%, gate 95%).
- Written 60 cells: FILL 15, CORRECTION 0, CONFIRM 45. Held 0 (none).
- Three pages: p10 and p11 (key-feature matrices with S or dash per trim) and p12 (specification table: fuel tank 37 L for the petrol engine and the petrol tank of the bi-fuel engine; the "CNG: 60 (Water equivalent)" line is not used, as the glossary now says).
- Only confirmations and fills: every feature cell already held the printed value, and the 15 fuel-tank cells were blank. A first extraction of p14 (not a specification page) returned nothing and is discarded.
- N4 (Exter editions 815/816), checked on p10 and p11: the table header reads HX 2, HX 3, HX 4, HX 4+, HX 6, HX 6 Knight, HX 8, HX 10, HX 10 Knight. The brochure lists Knight columns, not Dual Tone trims; its only Dual Tone line is the p11 note "DT-Dual Tone Option is available on select trims". So it does not confirm 815/816 as trims named "HX 6 Dual Tone" and "HX 10 Dual Tone" and P8 keeps them held: no re-base, no price change (815 stays ₹5.80 lakh on base HX 2, 816 ₹6.91 lakh on base HX 3; the KB's own HX 6 Petrol Manual is ₹7.95 lakh and HX 10 Petrol Automatic ₹9.42 lakh).
- P7 note: the brochure shows Knight columns the KB lacks as base variants. Writes are limited to the seven trim columns the KB has, which map one to one; the Knight columns are not written.

## Write [VERIFIED `apply_prod_log.txt`]
60 cells: 15 filled, 0 corrected, 45 confirmed; 60 OEM observations and provenance rows; 15 amendments; 0 existing quarantines on these cells released; 0 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, 0-byte -wal after `wal_checkpoint(TRUNCATE)`. Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the seven trim columns the KB has (HX 2, HX 3, HX 4, HX 4+, HX 6, HX 8, HX 10) are in the brochure; the brochure also prints HX 6 Knight and HX 10 Knight columns which are not written · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 29,676 / 30,713 / 41,892 / 33,743; run B per page 19,051.

## Not done / held
- Exter editions 815 and 816 stay held (P8): the brochure names Knight trims, not Dual Tone trims.
- Exter CNG km/kg (27.1, unverified since 10F): the brochure prints no km/kg.
- Mileage, head-up display, ventilated seats, drive modes: not on the pages read.
