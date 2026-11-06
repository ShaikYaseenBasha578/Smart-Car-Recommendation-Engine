# Phase 10N — local brochure enrichment, first batch
Date: 2026-11-06. Backlog item 8. No ingestion or network fetch.

| | |
|---|---|
| Prod before / after | `acf32b47e19c711d9f8bdc332132c5df6510c489` → `758310ea3ea1868dd94cebc9f9535b34719fd994` |
| Backup | `pre_phase10n_20261106T154455Z.db` |
| Script | `knowledge_base/db/migrations/apply_phase10n.py` + `phase10n_cells.tsv`; script SHA-1 `357fcd5f…` |

## Write [VERIFIED apply_prod_log.txt]
149 base-variant cells from 13 local brochures (all SHA-1s checked): 126 changed (70 blank filled, 56 corrected), 23 confirmed. 149 OEM observations and provenance rows, 126 amendments, 55 quarantines released (the brochure settles them), 58 contradicted provenance rows quarantined. Active quarantines 1,381. No schema change. Integrity ok; 297 FK orphans; prod diff equals dry-run diff (timestamps masked); re-run changes nothing.

## Validation (P12)
- **Round 1 FAILED for cruise control:** fresh blind subagent, 72 stratified cases. Mileage 24/24, wireless 24/24, **cruise 21/24 (87.5%)**. All three misses were my table's error: Victoris Zxi+ 6AT marked no cruise, because I read only the plain Cruise Control row and missed the ACC row printed "6AT" (p16). Not written. The failed table is kept as `phase10n_cells_v1_failed_cruise.tsv` in the scratch directory.
- **Fix:** 568, 569, 572, 573 set to 1. I re-read the other nine cruise "no" cells; none changed.
- **Round 2 PASSED:** a second fresh blind subagent read all 32 cruise cells not confirmed in round 1, including the 4 corrected: 32/32. Every cruise cell has now been agreed by a blind reader on the final value.
- **Limits of blindness:** the reader had no labels or code, but round 2 was sampled after the error was known, and the project CLAUDE.md loaded into its context (it reports not using it; it holds no values for these cells).
- **Judgement to note:** cruise_control=1 includes adaptive-only cars, matching Venue HX10 and Amaze ZX. Victoris AllGrip rests on the powertrain table listing AllGrip Select as 6AT; the ACC row does not name it.

## P7 check
Run after the apply, not before; the output arrived in the same command. Dzire 235 and Ertiga 211/214/215 are single-gearbox corrections; sibling rows already match the same brochure line, so these are one-off wrong values, not a model-year change. Victoris corrections cover all its non-hybrid petrol rows.

## P13
Not triggered: no body_type, fuel, transmission, seats or price cell written.

## App
Export twice identical (`42aa5901…`); 151 cells, equal to the whitelist; 353 tests passed. PR: https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/24

## Not done
Item 8 is only partly done. This batch covers mileage for Amaze, City, Dzire, Ertiga and Victoris, and cruise/wireless for the nine models read by hand. Most remaining gap cells (about 1,140 of about 1,290, an earlier estimate not recounted) are unfilled: HUD where brochures are silent, other models' cruise/wireless, Slavia, Tiago EV, City 302 features, Virtus and Victoris wireless.
