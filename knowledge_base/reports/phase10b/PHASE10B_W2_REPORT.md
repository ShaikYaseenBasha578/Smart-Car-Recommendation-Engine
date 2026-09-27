# Phase 10B W2 — B1 "absent written as 0" quarantine (controlled write)

**Date:** 2026-09-27. **Branch:** kb/phase-10-0-versioning. **Operation:** inserts into `evidence_quarantine` only; **no existing row updated or deleted.**

## Rule (owner decision, 2026-09-27): strict
A B1 zero is quarantined unless another source's **live, non-quarantined** evidence (`v_live_evidence`, i.e. after W1) gives 0 for the same (variant, field). A B1 zero is a `field_provenance` row with `decision='accepted'` and `accepted_value='0'` from V3Cars (3) or 91wheels (2).

- **V3Cars evidence never counts as corroboration, in any decision.** V3Cars maps "keyword not found" to 0 for every row (`field_map_v3cars.py:24`), so a V3Cars zero, whether accepted, confirmed or rejected, is not independent evidence of absence.
- Other B1 rows never corroborate each other.
- **CONTRADICTED:** another source's live evidence gives a non-zero value. A non-zero from V3Cars counts, because it means the keyword was found.
- **Reason codes:** `B1_ABSENT_AS_ZERO_SOLE` and `B1_ABSENT_AS_ZERO_CONTRADICTED`.
- **Masking:** each quarantine targets one variant cell (`target_field` set). `v_variant_canonical_q` masks it to NULL; `variant` is unchanged.

## Sensitivity: 310 vs 337
| Rule | SOLE | CORROBORATED | CONTRADICTED | W2 entries |
|---|---|---|---|---|
| Design rule: only other *B1* rows are excluded as corroboration | 290 | 100 | 20 | 310 |
| **Strict (applied): V3Cars zeros never corroborate** | **317** | **73** | **20** | **337** |
The 27 extra cells are zeros whose only corroboration was a V3Cars zero. For comparison, 10A (before W1) had 279 / 104 / 27.

## Artifacts
- **Entry builder** `knowledge_base/db/migrations/build_w2_entries.py`: read-only and deterministic. It encodes the rule above and was run on a /tmp snapshot of post-W1 production.
- **Entries** `knowledge_base/db/migrations/phase10b_w2_entries.csv`: 337 cells.

  | Field | Cells |
  |---|---|
  | wireless_charging | 130 |
  | heads_up_display | 114 |
  | cruise_control | 75 (19 contradicted) |
  | tyre_pressure_monitoring_system | 9 (1 contradicted) |
  | ventilated_front_seats | 9 |

- **Applier** `knowledge_base/db/migrations/apply_phase10b_w2.py`: the same as the W1 applier except for `PHASE='10B-W2'`. It runs one `BEGIN IMMEDIATE` transaction with `foreign_keys=ON`, skips any entry that is already active (idempotent), and checks invariants before `COMMIT`.
- **Backup** `knowledge_base/backups/pre_phase10b_w2_20260927T075058Z.db`:
  - file SHA-1 `363289b743e33ea03734a0407098cd46e478f05f`
  - content `.sha3sum` `76313d5c…398cb4`, which equals production before W2
  - `integrity_check` ok
  - also copied to Google Drive `My Drive/CarRec_backups/` (real File Provider mount), with the SHA-1 verified

## Diff vs backup (EXCEPT, both directions)
| Table | Isolated | Production |
|---|---|---|
| evidence_quarantine | +337 / −0 | +337 / −0 |
| sqlite_sequence | 1 modified: the evidence_quarantine counter went 347→684 (bookkeeping) | same |
| all 14 data tables, evidence_amendment, schema | 0 | 0 |

- The production diff file is byte-identical to the isolated one.
- **Idempotency:** the second run inserted 0 rows and the content `.sha3sum` was unchanged.

## Production apply
- **Before:** `lsof` was empty and SHA-1 was `6f35aa422e290fe7872c84bfb6e080e8584021b1`.
- **Apply:** COMMITTED with 337 rows inserted. `wal_checkpoint(TRUNCATE)` returned `0|0|0`. No side files were left and `lsof` was empty afterwards.
- **Post-checks:** `integrity_check` ok. `foreign_key_check` found 297 violations, all the known `field_provenance → source_observation` orphans.
- **New production SHA-1:** `f26db30f4b3eb47fd0c0e21eb3ee4829abf38c81`

## View effects
| | After W1 | After W2 |
|---|---|---|
| active quarantine entries | 347 | 684 |
| v_corroboration rows | 25,971 | 25,634 |
| v_live_evidence rows | 34,059 | 34,059 (W2 masks cells, not evidence) |
| variant rows differing between v_variant_canonical_q and v_effective_variant | 12 | 172 |
- W1 and W2 cells do not overlap.
- All 337 W2 cells read NULL in `v_variant_canonical_q`.

## Not in W2
- The 73 CORROBORATED zeros stay canonical.
- Whether any quarantined zero is actually true (feature absent) is **UNDETERMINABLE** from the DB. A release requires external evidence and a separate controlled write.
