# Phase 10B W6: canonical corrections from the human-verified OEM spot-check (controlled write)

**Date:** 2026-09-29. **Branch:** kb/phase-10-0-versioning. **Authorised by the owner in session**, including every scope decision below.

**Scope:** correct canonical `variant` cells to the brochure values the owner verified in the Phase 10C-1 spot-check (`knowledge_base/reports/phase10c/OEM_SPOTCHECK_SHEET.csv`, commit b84444c), and quarantine the live evidence that contradicts those values.
- 22 cells were derived from the sheet. **12 were applied and 10 were held** under CATALOG_CURRENCY (see below).
- `field_provenance` was **not** modified. The original OEM `rejected` decisions stay as history; the amendment rows record the supersession.

Claims below are [VERIFIED] against the production copy, the backup or the committed CSVs unless tagged otherwise. Git has no KB history; state is established by backups and hashes.

## Target derivation
`knowledge_base/db/migrations/build_phase10b_w6_targets.py` reads only the sheet and the verification aid's page links, with no DB access.
- A target is a sheet row where the normalised `true_value` (✓/●/■/Standard/True → 1, –/False → 0) differs from `current_canonical_value`.
- **22 derived targets:** the 21 REJECTED_WOULD_FLIP rows with verdict CORRECT, plus #26 (Virtus sunroof, verdict WRONG, extracted junk `[Vector:Curve]`, verified 1). #24 and #25 are not targets because canonical already equals the verified value 1.
- Output: `phase10b_w6_targets.csv` (12 applied) and `phase10b_w6_held.csv` (10 held, each with `hold_reason`).
- **Amendment notes (owner decision B(a), no DDL):** `evidence_amendment` has no `note` column. Each cell's note is in the targets CSV, keyed by (variant_id, column, phase `10B-W6`), in this form: `provenance_id=…; sheet_row=…; human-verified against brochure p.N (page located by verification aid)`. The page numbers come from the verification aid, not from the reviewer's sheet, whose `page_numbers` column is blank.

## Precheck (read-only, /tmp copy of production `df9e2d9b…`)
1. **Quarantine:** none of the 22 cells has an active or released quarantine row, for the field or `'*'`.
2. **Edition inheritance:** edition 821 ("Zxi Petrol 1.0L Turbo Manual Dual Tone", base 142 Brezza ZXi MT) inherits `hill_assist` and `connected_car_features`.
   - The owner first chose to accept propagation, after confirming that the Brezza brochure is post-update and that its ZXi column covers the Turbo ZXi with no "(Turbo)" qualifier on those rows.
   - The owner then held all Brezza cells (see CATALOG_CURRENCY), so **W6 does not change 821**. No applied target has an inheriting edition.
3. **Drift:** all 22 current values equal the sheet's `current_canonical_value`.

## Change (applied)
| Sheet row | Variant | Column | Old → new | Page |
|---|---|---|---|---|
| 1 | 270 Hyundai Aura S MT | tyre_pressure_monitoring_system | 0 → 1 | 9 |
| 2 | 271 Hyundai Aura SX MT | hill_assist | 0 → 1 | 9 |
| 3 | 274 Hyundai Aura SX(O) MT | hill_assist | 0 → 1 | 9 |
| 16 | 60 Maruti Suzuki Swift VXi (O) Petrol Manual | hill_assist | 0 → 1 | 6 |
| 17 | 669 Skoda Kylaq Classic Petrol Turbo Manual | tyre_pressure_monitoring_system | 1 → 0 | 23 |
| 18 | 669 Skoda Kylaq Classic Petrol Turbo Manual | hill_assist | 1 → 0 | 23 |
| 19 | 671 Skoda Kylaq Classic Plus Petrol Turbo Manual | tyre_pressure_monitoring_system | 1 → 0 | 23 |
| 20 | 671 Skoda Kylaq Classic Plus Petrol Turbo Manual | hill_assist | 1 → 0 | 23 |
| 21 | 671 Skoda Kylaq Classic Plus Petrol Turbo Manual | android_auto | 1 → 0 | 25 |
| 22 | 671 Skoda Kylaq Classic Plus Petrol Turbo Manual | apple_carplay | 1 → 0 | 25 |
| 23 | 677 Skoda Kylaq Signature Petrol Turbo Manual | hill_assist | 1 → 0 | 23 |
| 26 | 642 Volkswagen Virtus Highline Plus Petrol 1.0L Turbo Manual | sunroof | 'False' → 'True' | 14 |

- **Amendments:** one `evidence_amendment` row per cell, reason `OEM_SPOTCHECK_VERIFIED`, phase `10B-W6`, ids 58–69.
- **Kylaq:** the brochure is hosted on CarTrade, not the OEM site. The owner confirmed the Kylaq update only added a Sportline variant and left existing trims unchanged, so rows 17–23 were applied.
- **Quarantine** (owner decision (b)), ids 686–698: 13 rows, `target_table='field_provenance'`, `target_field` NULL (the convention for non-variant targets), reason `CONTRADICTED_BY_OEM_SPOTCHECK`, phase `10B-W6`. Built by `build_phase10b_w6_quarantine.py` from a /tmp copy; the list is `phase10b_w6_quarantine.csv`.
  - 12 are `v6_migration` `accepted` rows that hold the pre-correction value.
  - **fp 31808** (`v3cars`, `confirmed`, `'0'`, on 642 sunroof) is quarantined under the **W2 rule**: V3Cars maps "keyword not found" to 0 (`field_map_v3cars.py:24`), so a V3Cars zero is not independent evidence of absence. The rule is recorded in the row's note.
- **Effect:** the 12 corrected cells now have **no** `v_corroboration` row. The verified value is backed by the amendment row and the OEM `field_provenance` rows, which stay `rejected`. That is the honest state; no corroboration is claimed that the evidence does not support.

## Held (CATALOG_CURRENCY), not written
| Sheet rows | Variants | Reason |
|---|---|---|
| 5, 6, 7, 8, 10, 11, 13, 14, 15 | Brezza 138, 140, 142, 145 | V6 rows observed 2026-06-22, before the July 2026 update; brochure created 2026-07-27 (post-update) |
| 4 | Baleno 247 | V6 rows observed 2026-06-22, before the facelift; brochure created 2026-09-05 (post-facelift) |
These cells get no amendment and no quarantine rows. Their verified values stay in the sheet for when a model-year dimension exists.

## Backup
- `knowledge_base/backups/pre_phase10b_w6_20260928T194755Z.db`: made with `.backup` from a /tmp snapshot whose SHA-1 equalled production (`df9e2d9b…`).
  - File SHA-1 `f2cf68844100a6586db06afdf834d649c678426a`.
  - Content `.sha3sum` `3e8f16d5…f9cc1`, equal to production before W6.
  - `integrity_check` ok.
- Copied with `cp -p` to Google Drive `My Drive/CarRec_backups/`; SHA-1 verified identical.

## Diff vs backup (EXCEPT, both directions; isolated == production)
| Object | Diff |
|---|---|
| variant | 12 cells in 8 rows; only the target columns (`updated_at` untouched) |
| evidence_amendment | +12 |
| evidence_quarantine | +13 |
| sqlite_sequence | amendment 57 → 69, quarantine 685 → 698 (bookkeeping) |
| field_provenance, every other table, schema | 0 |
| v_variant_canonical_q | 12 cells, exactly the targets |
| v_live_evidence | −13 (the quarantined rows) |
| v_corroboration | −12 rows, exactly the target cells |
| v_observation_status, v_safety_applicability_q | 0 |

- **Idempotency:** a second isolated run made 0 updates and 0 inserts; the content hash and the diff output were unchanged.
- **Production diff:** the output of `diff_phase10b_w6.py` on production is byte-identical to the isolated one. The full-table comparison of production against the isolated copy shows no difference beyond the `created_at` of the new rows.

## Production apply
- **Pre-apply:** SHA-1 `df9e2d9b391aa1b50edc42e27ccd63911345adf5`; `lsof` empty; no side files.
- **Apply:** `apply_phase10b_w6.py` ran as one `BEGIN IMMEDIATE` transaction with `foreign_keys=ON`. It asserted before COMMIT:
  - no active variant quarantine on any target;
  - old values as expected and each quarantined fp row unchanged;
  - only the listed variant cells changed;
  - only `evidence_amendment` and `evidence_quarantine` gained rows, exactly the new ones;
  - `v_variant_canonical_q` and `v_corroboration` changed only on the target cells;
  - `integrity_check` returned ok.
- **Result:** COMMITTED (12 updates, 13 quarantine inserts).
- **Post-checks:** `integrity_check` ok; `foreign_key_check` shows only the known 297 orphans (`field_provenance → source_observation`); `wal_checkpoint(TRUNCATE)` returned `0|0|0`; no side files remain.
- **New production SHA-1: `8592508789594ab76cf98e463bbf77606a76a7e2`.**

## CATALOG_CURRENCY log (open; not fixed in W6)
The KB has no model-year dimension: V6 rows are pre-update snapshots, while later sources (brochures, CarWale) describe the current catalogue. **The KB needs a model-year dimension** before these can be resolved.
1. **Brezza 138–147 and edition 821.**
   - The V6 rows (observed 2026-06-22) predate the July 2026 update, which added the 1.0L Turbo Boosterjet and a new 6MT. The brochure ("The New Brezza Brochure", created 2026-07-27) is post-update. The 9 W6 cells are held.
   - 821 is a post-update variant on a pre-update base. Its `powertrain_id` is 15 (1462 cc K15), which contradicts its "1.0L Turbo" name.
   - CarWale 1.0 Turbo observations **3240** (ZXi) and **3245** (ZXi+) resolved to base 142.
2. **Baleno.** The V6 rows (2026-06-22) are pre-facelift; the brochure ("The Stunning New Baleno", 2026-09-05) is post-facelift. Row 4 is held.
3. **Kylaq Sportline missing from the KB.** Kylaq has 11 variants (669–679), none of them Sportline, although the brochure includes Sportline.
   - Sportline observations were resolved to Prestige instead: CarWale **3446** → 673 (live) and 3450 → 673 (already quarantined).
4. **Follow-up (separate item): V3Cars resolution path needs the same audit as CarWale.**
   - V3Cars Sportline observations **2350** → 673 (Prestige MT) and **2354** → 672 (Prestige AT) are misresolved to Prestige, the same failure as CarWale 3446.
   - The Phase 10C-2 resolver fix covered CarWale only, so the V3Cars resolver needs the same audit.
   - The **13 live accepted/confirmed `field_provenance` rows** these Sportline observations put on Prestige 672/673 (2350: 3, 2354: 4, 3446: 6) are **candidates for a follow-up quarantine write**, not W6.

## W7 log: value-blind corroboration (measured, not fixed)
`v_corroboration` counts distinct sources over live accepted/confirmed evidence per (variant, field) without comparing the value to canonical, so evidence that disagrees counts as corroboration KB-wide. Measured read-only with `knowledge_base/reports/phase10b/measure_w7_corroboration_value_blind.py`, comparing each counted source's values with `v_variant_canonical_q`.

| State | v_corroboration cells | ALL_DISAGREE (strict) | ALL_DISAGREE (No/Yes normalised) | MIXED | NO_CANONICAL | cells counting a V3Cars zero |
|---|---|---|---|---|---|---|
| Before W6 (backup) | 25,634 | 283 | 3 | 0 | 168 | 913 |
| After W6 (production) | 25,622 | 283 | 3 | 0 | 168 | 912 |

- **Strict comparison:** 280 of the 283 cells are `drive_modes`. The evidence says 'No' where canonical is integer 0: an encoding mismatch, not a disagreement. The 168 NO_CANONICAL cells are also `drive_modes` ('Yes[n]' evidence against a NULL canonical).
- **Real disagreements (3):** 821 `sunroof`, 822 `cruise_control` and 822 `heads_up_display`. Each is canonical 0, corroborated only by CarWale (source 4) saying 1.
- **Second defect, V3Cars zeros:** `v_corroboration` does not apply the W2 rule. 912 cells still count a V3Cars zero as a corroborating source, so each is overstated by 1. None depends on V3Cars alone.
- **Fix for W7:** make `v_corroboration` compare the value with canonical and exclude V3Cars zeros. This is a view change that needs its own approval.

## Technical debt
- `sunroof` is stored as TEXT `'True'`/`'False'` (809 of 818 non-null rows; 7 `'0'` and 2 `'1'`), while every other feature column is INTEGER 0/1. W6 wrote `'True'` to match the column's convention (owner decision C).

## Artifacts (committed)
- `knowledge_base/db/migrations/build_phase10b_w6_targets.py` → `phase10b_w6_targets.csv` (12 applied), `phase10b_w6_held.csv` (10 held)
- `knowledge_base/db/migrations/build_phase10b_w6_quarantine.py` → `phase10b_w6_quarantine.csv` (13 rows)
- `knowledge_base/db/migrations/apply_phase10b_w6.py`: the applier, idempotent.
- `knowledge_base/db/migrations/diff_phase10b_w6.py`: the diff, read-only.
- `knowledge_base/reports/phase10b/measure_w7_corroboration_value_blind.py`: the W7 measurement, read-only.
