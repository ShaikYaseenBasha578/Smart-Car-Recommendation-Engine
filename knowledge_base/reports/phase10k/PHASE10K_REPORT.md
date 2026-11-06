# Phase 10K — brochure qualifiers dropped from feature tables (backlog item 3)

**Status: APPLIED to prod (2026-11-06 15:18 UTC).** Prod SHA-1 `2623fa7af76f02f846e5de8603cb5e2b14eafde2` → `459e4a995ad5a52622e98e26449f36772dcd28ae`.

## 0. Access
P11 held (`apply_prod_log.txt`). Brochure SHA-1s re-hashed: all 5 match.

## 1. Backup
See `backup_log.txt`: `.backup` from a verified byte copy, `.sha3sum` equal.

## 2. How the scan worked
- `scan.py`: qualifiers in the raw payloads of 52 OEM-extracted observations (60 hits, all consistent with stored values or covered below).
- `scan2.py`: every brochure on disk, table rows combining a mapped feature with a qualifier (111 rows, `qualifier_rows.txt`).
- `q3.sql`: stored values that could contradict them. Each candidate page was then rendered and read. The scan only found candidates; **no cell was decided by a heuristic**, so P12 doesn't apply.

## 2a. Change table (16 cells; exact printed text per cell in `apply_phase10k.py`)
| Variant | Field | Old → new | Source |
|---|---|---|---|
| Kushaq 605 Classic Plus MT | paddle_shifters, cruise_control | 1 → 0 | `kushaq_brochure.pdf` p27 "AT only" |
| Venue 150, 151, 154, 155, 156 | cruise_control | 1 → 0 | `hyundai_venue_brochure.pdf` p20 |
| Grand i10 Nios 261 Corporate AMT | esc | 0 → 1 | `Grand_i10_Nios_Brochure.pdf` p10 "AMT only" |
| Grand i10 Nios 259, 260, 264, 266 | hill_assist | 0 → 1 | same page: S on Sportz, Sportz (O), Asta |
| Victoris 570, 574 strong hybrid | cruise_control | 0 → 1 | `maruti_suzuki_victoris_brochure.pdf` p16 (rendered) |
| Tiago 364, 365 CNG AMT | cruise_control | 1 → 0 | `tata_tiago_brochure.pdf` p28 footnote |

19 live provenance rows the brochures contradict were quarantined (`CONTRADICTED_BY_OEM_BROCHURE`).

## 3. Verification
Dry run and prod: 16 corrected, 16 amendments, 16 observations, 16 provenance rows, 19 quarantines; 1,380 active. `EXCEPT` diff: schema identical; 15 variant rows (605 has two cells). Idempotency: empty diff. Prod diff equals the dry-run diff (timestamps masked). `integrity_check` ok; 297 FK orphans; checkpoint 0|0|0. P13: no paper field touched.

## 6. Schema
None.

## 7. App
`app/kb-10k-export`, stacked on `app/kb-10j-export`. Catalogue SHA-1 `11b3f34b…`, two identical runs; the diff is exactly the 16 cells; 352 tests passed.

## 8. Prod SHA-1
`2623fa7a…` → `459e4a99…`.

## 10. Held or checked with no change
- Jimny 599 paddle shifters = yes on a manual: the Jimny brochure doesn't mention paddle shifters (P9; Jimny catalogue currency). Edition 824 inherits it.
- Nios 258 Magna AMT: the brochure has no Magna AMT (P7/P9).
- Virtus Highline and Highline Plus MT cruise = yes: correct, its row (p10) has no qualifier, unlike Taigun's.
- Blank cells beside qualifiers (Gravite AMT, Victoris AT, Aura SX+): item 8.
