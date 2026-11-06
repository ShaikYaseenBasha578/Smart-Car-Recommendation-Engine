# Phase 10J — brochure correction of the 10H sole-source cells (backlog item 2)

**Status: APPLIED to prod (2026-11-06 15:12 UTC).** Prod SHA-1 `9bf0bc7a23bc95508968abe2025ceae3787a1bed` → `2623fa7af76f02f846e5de8603cb5e2b14eafde2`.

## 0. Access
P11: only the read-only VM holder; no side files; SHA-1 rechecked immediately before; `integrity_check` immediately after (`apply_prod_log.txt`).

## 1. Backup
`knowledge_base/backups/pre_phase10j_20261106T151256Z.db`; `.sha3sum` `ddaccfb0…` equal (`backup_log.txt`). Brochure SHA-1s re-hashed: all 9 match.

## 2. Change tables
Every value comes from the variant's own brochure (P1). Pages were rendered and read where the layout matters. Script: `knowledge_base/db/migrations/apply_phase10j.py` (exact PDF, page, SHA-1, printed text per cell).

**Corrected (8):** Amaze 293 km/l 19.46 → 18.65 (p27); Dzire 237 km/l 25.71 → 24.79 (p5); Ertiga 210 km/l 20.3 → 20.51 (p7, rendered: image-only); Taigun 630, 632 cruise control yes → no (p10, "AT only"); Harrier 452 sunroof no → yes (p18); Harrier 453, 457 TPMS yes → no (p19: first listed at Fearless X).

**Confirmed (17):** cruise control on Harrier 452, 453, 457, 458, 460, 462, Taigun 629, 631, Syros 757, Clavis EV 804, Punch EV 746 (no), Tiago EV 742 (no); TPMS on Harrier 452 (no), 458, 460, 462; ADAS on Harrier 453 (no).

A feature counts as absent only where the brochure's own "features over the lower trim" cascade adds it at a higher trim.

**Stay quarantined (22):**
| Cells | Why |
|---|---|
| HUD: Altroz 343, Harrier 452, 453, 458, Taigun 630 | brochure doesn't mention a head-up display (P9; not mentioned is unknown) |
| Ventilated seats: XUV 3XO 36, 41, 50, 52, 54 | brochure doesn't mention them (P9) |
| Km/l: Baleno 252, Brezza 146 | catalogue currency: the Baleno brochure prints 23.80 / 24.77 against KB rows at 22.35 / 22.94, and Brezza is in the same hold (P7) |
| Km/l: Innova Crysta 306, XUV 7XO 416 | brochure prints no mileage (Crysta text layer; XUV 7XO p30 rendered) (P9) |
| Editions 821 ×3, 831 ×3, 832 ×2 | edition cells are never written (P8) |

## 3. Verification
Dry run on a fresh copy, then prod: `{"corrected": 8, "confirmed": 17, "amend": 8, "obs": 25, "fp": 25, "released": 25}`, 1,361 active quarantines. `EXCEPT` diff: 8 amendments, 25 quarantine rows released, 25 observations, 25 provenance rows, 8 variant rows, sequence counters; schema identical. Idempotency: empty diff. Prod diff equals the dry-run diff (timestamps masked). `integrity_check` ok; 297 FK orphans; checkpoint 0|0|0.

P12: not a classifier; each cell was read by hand. P13: no paper field touched.

## 6. Schema
None.

## 7. App
`app/kb-10j-export`, catalogue SHA-1 `92c30c0a…` (two identical runs). Diff: 27 cells on 18 rows (25 + 2 inherited by edition 831); `unverified_fields` consistent; 352 tests passed.

## 8. Prod SHA-1
`9bf0bc7a…` → `2623fa7a…`.

## 10. Found in passing, for later items
Ertiga AT rows hold 18.69 (brochure 20.30); Dzire 235 VXi AMT holds 22.0 (brochure 25.71). Amaze CVT, Dzire and Ertiga blanks: item 8.
