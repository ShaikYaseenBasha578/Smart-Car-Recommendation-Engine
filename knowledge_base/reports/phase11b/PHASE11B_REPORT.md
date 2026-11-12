# Phase 11B — enrichment batch 2: Tata Nexon (feature cells)
Date: 2026-11-12. Second batch of the Claude-only enrichment loop (`kb/enrich-claude`). No ingestion, no network, no schema change.

| | |
|---|---|
| Prod before / after | `795a12233ee84147990f00e36816bfe841beb281` → `afad3a5fecefa98335cdb1db91c9f4528b8aab55` |
| Backup | `pre_phase11b_20261112T143457Z.db` |
| Script | `knowledge_base/db/migrations/apply_enrich.py` + `cells.tsv` (script SHA-1 `6b7d2367…`) |
| Source | `tata/nexon/latest/brochures/tata_nexon_brochure.pdf` p38, p39, p40, SHA-1 `4485b42444e6ec4ad332c34e53d3e4ec2c418820` |

## Extraction [VERIFIED `classified.tsv`]
- Three pages (persona lists p38/p39, specification p40), 53 base variants, fields per page chosen by keyword (p38 cruise and paddle, p39 cruise, wireless and ventilated seats, p40 cruise) = 318 cells.
- Run A read every cell. Run B (blind, own folder, no run-A output) answered only the 23 validated pairs: 13 corrections and 10 sampled fills. They agreed on 23 of 23.
- Classes after guards: written 143 (FILL 12, CORRECTION 3, CONFIRM 128); held 28.
- Held: 11 cruise-control cells (10 corrections 1 → 0 and one fill) that rest only on the page-bottom "*Disclaimer: Available in AMT / DCA", whose scope the page doesn't tie to the Cruise Control line (P6; owner decision on N10); 15 cells where p38/p39 and p40 disagree (Pure + PS cruise: p38 lists it, p39's cumulative list does not, p40 says not available in CNG); 2 zeros for a feature never shown fitted on the page.
- Mileage: no page prints km/l (not written, P9).

## Write [VERIFIED `apply_prod_log.txt`]
143 cells: 12 filled, 3 corrected, 128 confirmed; 143 OEM observations and provenance rows; 15 amendments; 14 existing quarantines on these cells released (the brochure settles them); 3 contradicted provenance rows quarantined. Dry run, idempotency re-run (0 changes), prod diff equal to the dry-run diff (timestamps masked), integrity ok, 297 FK orphans, `wal_checkpoint(TRUNCATE)` then a 0-byte -wal (P11 as amended on 2026-11-12). Schema unchanged.

## Policy checks
P1 cited file/page/SHA-1 (checked by the script) · P7 the page's persona columns (Smart … Fearless + PS) match the KB trims · P8 every written cell is on a base variant (the script asserts it) · P9 n/a · P13 not triggered (no body, fuel, transmission, seats or price cell) · qualifiers applied by gearbox/fuel (not available in CNG).

## Tokens [VERIFIED `usage_a.tsv`, `usage_b.tsv`]
Run A per page 46,791 / 42,033 / 42,896; run B per page 25,806 / 31,683 / 17,157 (B answered 1, 19 and 3 pairs).

## Not done / held
Nexon km/kg on CNG (the brochure refers to a separate iCNG brochure), mileage, HUD, paddle shifters beyond p38 and the new fields fuel tank and drive modes (added to scope after this batch; supplement pass pending).
