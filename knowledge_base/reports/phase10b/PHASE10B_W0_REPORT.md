# Phase 10B, W0: quarantine and amendment schema (controlled write)

**Date:** 2026-09-27
**Branch:** kb/phase-10-0-versioning
**Design:** PHASE10B0_QUARANTINE_DESIGN.md (option B, commit 373efae), plus the owner decisions of 2026-09-27.
**Scope:** schema only. **No existing row, table, index or view was modified.**

## Artifacts
- **DDL:** `knowledge_base/db/migrations/phase10b_w0_schema.sql`. Idempotent; every statement is `IF NOT EXISTS`.
- **Applier:** `knowledge_base/db/migrations/apply_phase10b_w0.py`. It runs one `BEGIN IMMEDIATE` transaction with `foreign_keys=ON`, checks its invariants before `COMMIT`, and rolls back if any check fails.
- **Backup:** `knowledge_base/backups/pre_phase10b_w0_20260927T012954Z.db`.
  - File SHA-1: `af013d38d1dc0c76d91f13905ee2adf8827911df`.
  - Content `.sha3sum`: `fd3cd81b…2a8585`, which equals production before W0.
  - It was made with `.backup` from a `/tmp` snapshot and passes `integrity_check`.

## Objects created
| Type | Name |
|---|---|
| table | `evidence_quarantine` (CHECKs: target_table is one of 5 tables; target_field is required for `variant`; a release requires a reason) |
| table | `evidence_amendment` |
| index | `ux_quarantine_active` (unique, partial: active quarantines only) |
| index | `ix_amendment_target` |
| view | `v_active_quarantine` |
| view | `v_live_evidence` (drops the 297 orphans and any quarantined observations or provenance) |
| view | `v_corroboration` (counts distinct live sources) |
| view | `v_variant_canonical_q` (same columns as `v_effective_variant`, with quarantined cells masked; masks on a base variant propagate to editions that inherit from it) |
| view | `v_observation_status` (5-value vocabulary) |
| view | `v_safety_test_status` (5-value vocabulary; added at the owner's request) |

Owner decision applied: observations 3721, 3722, 3756 and 3757 and tests 1, 2, 36 and 37 (Citroen ×2, VinFast ×2) map to `no_match` with reason `manufacturer_not_in_kb`. These IDs are hard-coded on purpose. Matching on the justification text would be wrong, because Brezza and Dzire carried the same text before 9B.

## Isolated checks (on a `/tmp` copy of the pre-W0 snapshot)
- **Per-table EXCEPT diff against the backup, both directions:** 0 row differences in all 14 existing tables (including `sqlite_sequence`). Objects added: the 10 listed above. Removed: none. Existing object SQL changed: 0.
- **Idempotency:** the second run of the applier added no objects and raised no errors. The content `.sha3sum` was `0e79cf63…afb81d9` after both runs.
- **Views with no quarantine entries:**
  - `v_active_quarantine`: 0 rows.
  - `v_live_evidence`: 36,148 rows (36,445 − 297), with 0 differences against a direct join.
  - `v_corroboration`: 26,010 rows, with 0/0 differences against a direct aggregate.
  - `v_variant_canonical_q`: 832 rows, with 0/0 differences against `v_effective_variant`; the column list is identical.
  - `v_observation_status`: 3,451 rows, none unmapped.
  - `v_safety_test_status`: 37 rows, none unmapped.
  - The only test/observation status disagreements are tests 9, 16 and 17, the known B6 rows due for W3.
- **Masking test** on a throwaway copy, deleted afterwards:
  - quarantining a base cell masked it on the base (649) and on the edition that inherits it (814);
  - quarantining observation 2842 removed its 8 provenance rows from `v_live_evidence`;
  - after a release, 0 differences remained.

## Production apply
- **Before:** `lsof` empty; SHA-1 `1e3eb6795452860276eca24e7dd1f52e85e67a93`.
- **Apply:** the applier returned COMMITTED with the 10 new objects. `PRAGMA wal_checkpoint(TRUNCATE)` returned `0|0|0`. No `-wal` or `-shm` file remains, and `lsof` is empty.
- **After** (checked on a `/tmp` copy of post-W0 production):
  - `integrity_check`: ok.
  - `foreign_key_check`: 297 violations, all `field_provenance → source_observation` (the known orphans).
  - The diff against the backup is **identical to the isolated diff**: 0 row differences, the same 10 objects. The schema is identical to the isolated copy, and the content `.sha3sum` is the same (`0e79cf63…`).
- **New production SHA-1:** `2c04286ac891f85db549cfe73125bd639e06f16c`. This is recorded in CLAUDE.md, which now also carries the read-path rule.

## Follow-ups (not done in W0)
- `knowledge_base/schema/live_schema.sql` and the production SHA-1 header in `knowledge_base/manifests/artifact_checksums.sha256` still describe the pre-W0 state. They should be regenerated in a docs-only commit.
- W1 (B3 quarantine) has not started.
