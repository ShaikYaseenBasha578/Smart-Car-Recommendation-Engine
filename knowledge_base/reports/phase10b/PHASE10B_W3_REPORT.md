# Phase 10B W3: B5 + B6 BNCAP status fixes (controlled write)

**Date:** 2026-09-27. **Branch:** kb/phase-10-0-versioning.
**Scope:** B5 and B6 from PHASE10A_BUG_IMPACT.md. **No row deleted.** The only column changed is `resolution_status`, on the 5 listed rows.

## Changes
| Bug | Target | Change | Logged |
|---|---|---|---|
| B5 | safety_test 27 (TATA – HARRIER.EV) | resolution_status RESOLVED → NO_MATCH | evidence_amendment |
| B5 | source_observation 3747 (its observation) | RESOLVED → NO_MATCH | evidence_amendment |
| B5 | safety_test_applicability 14 (test 27 → model 30, MODEL_LEVEL) | **kept**, quarantined (`B5_EV_TEST_ON_ICE_MODEL`) | evidence_quarantine |
| B6 | source_observation 3729, 3736, 3737 (tests 9, 16, 17) | UNRESOLVED → RESOLVED | evidence_amendment ×3 |

- Test 33 (FAMILY_LEVEL Safari/Harrier) and its applicability row 19 are untouched.
- Why B5 is wrong: model 30 "Harrier" has only Diesel (14) and Petrol (12) variants, so an EV crash test was applied to an ICE-only model.
- Reason codes: `B5_EV_TEST_ON_ICE_MODEL` (as specified by the owner; the design doc's placeholder was `B5_WRONG_POWERTRAIN_SCOPE`) and `B6_STATUS_SYNC_AFTER_9B`. Phase: `10B-W3`.

## Artifacts
- `knowledge_base/db/migrations/phase10b_w3_entries.csv` has 6 actions, each with its expected old value.
- `knowledge_base/db/migrations/apply_phase10b_w3.py` does the following:
  - runs one `BEGIN IMMEDIATE` transaction with `foreign_keys=ON`;
  - aborts if any row is not in its expected old state;
  - skips any update that is already applied (no amendment row) and any quarantine that is already active;
  - before `COMMIT`, snapshots every table and checks four things: no rows are added or deleted outside `evidence_*`; the only changed column is `resolution_status` on the listed rows; +5 amendment rows and +1 quarantine row; `integrity_check` passes.
- **Backup:** `knowledge_base/backups/pre_phase10b_w3_20260927T080046Z.db`
  - file SHA-1 `aea38d81b28994fa0612a9b45e917078b3013da5`
  - content `.sha3sum` `bfb63a4f…ffe32`, equal to production before W3
  - `integrity_check` ok
  - copied to Google Drive `My Drive/CarRec_backups/` (real File Provider mount), SHA-1 verified

## Diff vs backup (EXCEPT, both directions): isolated == production
| Table | Diff |
|---|---|
| safety_test | 1 modified |
| source_observation | 4 modified |
| evidence_quarantine | +1 |
| evidence_amendment | +5 |
| sqlite_sequence | +1 counter row (evidence_amendment); evidence_quarantine counter 684→685 (bookkeeping) |
| every other table, schema | 0 |

- Idempotency: the second run made 0 updates and added 0 quarantine or amendment rows, with an unchanged content hash.
- The production diff file is byte-identical to the isolated one.

## Status consistency
- `v_safety_test_status` vs `v_observation_status` disagreements: **3 before, 0 after**. Test 27 is now `no_match`. Tests 9, 16 and 17 are `resolved_model`.

## Production apply
- Pre-apply SHA-1: `f26db30f4b3eb47fd0c0e21eb3ee4829abf38c81`. `lsof` was empty.
- COMMITTED; `wal_checkpoint(TRUNCATE)` returned `0|0|0`; no side files remain.
- `integrity_check` ok. `foreign_key_check` shows only the known 297 `field_provenance → source_observation` orphans.
- **New production SHA-1: `516c50651d3e97871c2f7566ce1db712566a63b4`.**

## Known gap, addressed by W3b
No existing view hid quarantined applicability rows, so a raw read of `safety_test_applicability` still returns row 14. W3b adds `v_safety_applicability_q`.
