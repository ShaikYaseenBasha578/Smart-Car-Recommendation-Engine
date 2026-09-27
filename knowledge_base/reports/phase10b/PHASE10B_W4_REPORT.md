# Phase 10B W4: B2 OEM source re-attribution (controlled write)

**Date:** 2026-09-27. **Branch:** kb/phase-10-0-versioning.

**Scope:** B2 from PHASE10A_BUG_IMPACT.md. The owner decided on re-attribution only:
- no decision was re-evaluated;
- no authority was re-tiered;
- no quarantine was added.

## Precheck (read-only, on a /tmp copy of production `2a315b31…`)
1. Source 6 is `oem` (source_type `oem`, authority_tier 1). Source 1 is `v6_migration`. Before W4 there were 0 observations under source 6.
2. Exactly 52 observations match `id BETWEEN 3669 AND 3720 AND source_id=1 AND source_url='offline_brochure'`. They are the only `offline_brochure` rows.
3. No other table stores a source reference for these observations.
   - `field_provenance` (133 rows) links only through `source_observation_id`.
   - `safety_test`, `evidence_quarantine` and `evidence_amendment` have no references to them.
   - `variant_alias` uses only sources 2 and 4.

## Change
- `source_observation.source_id` 1 → 6 on ids 3669–3720 (52 rows). No other column changed.
- One `evidence_amendment` row per update: old `1`, new `6`, reason `B2_OEM_SOURCE_REATTRIBUTION`, phase `10B-W4`.

## Recorded decisions and effects
**1. Historical decision texts are left unchanged.**
- 28 rejected `field_provenance` rows on these observations carry `decision_reason` text that encodes the tier used at decision time, when the observations were attributed to source 1 (`v6_migration`, code tier 5):
  - `conflict_field_tier_5_vs_best_5` (26 rows)
  - `conflict_field_tier_5_vs_best_3` (2 rows)
- These texts are historical: they describe how the decision was made under the old attribution. They were deliberately **left unchanged**, and the decisions themselves (104 confirmed, 28 rejected, 1 accepted) were not re-evaluated.
- Under correct attribution (OEM, tier 1), all 28 rejections would flip to accepted. At least 5 of those values are extraction junk: `'Standard'`, `'[Vector:Curve]'`. See PHASE10A B2. Any re-evaluation is future work that needs its own approval.

**2. `v_corroboration` shift.** `v_corroboration` counts distinct sources. Before W4, OEM and V6-migration evidence were merged under source 1. After W4 (production, compared with the backup):
- **99 cells gained one corroborating source.** They had both V6 and OEM accepted/confirmed evidence, now counted as sources 1 and 6.
- **3 cells were relabelled:** source 1 → 6, with the same count. OEM was their only source-1 evidence.
- The row count is unchanged at 25,634.

**The quality of the OEM extraction is still pending the spot-check.** The OEM observations' `raw_name`s ("V O O", "SV - - -") show that brochure column alignment is unverified. The +1 corroboration on those 99 cells should be treated as provisional until the spot-check confirms extraction quality. If the spot-check fails, the remedy is a separate controlled quarantine write with reason `B2_OEM_EXTRACTION_REVIEW`.

**3. Unchanged:**
- `v_variant_canonical_q` has 0/0 differences against the backup in both directions.
- `v_observation_status` has 0 canonical-status changes (a `resolved` row under source 6 still maps to `resolved_variant`).
- `v_safety_applicability_q` has 0/0 differences.

## Artifacts
- `knowledge_base/db/migrations/phase10b_w4_entries.csv`: 52 rows, each with its expected old value.
- `knowledge_base/db/migrations/apply_phase10b_w4.py`:
  - runs as one `BEGIN IMMEDIATE` transaction with `foreign_keys=ON`;
  - requires source 6 = `oem` and every row to have `offline_brochure`;
  - skips rows already at 6, so a re-run is idempotent.
  - Before COMMIT it asserts four invariants:
    - only `source_observation.source_id` changed, and only on the listed rows;
    - `evidence_amendment` gained exactly the number of updates;
    - `v_variant_canonical_q` is unchanged;
    - `integrity_check` returns ok.
- Backup `knowledge_base/backups/pre_phase10b_w4_20260927T080859Z.db`:
  - file SHA-1 `8117f16ed67d94273a5d29c8a70b79e2abf69a11`;
  - content `.sha3sum` `26ee0895…50fc0a`, which equals production before W4;
  - `integrity_check` ok;
  - copied to Google Drive `My Drive/CarRec_backups/` (the real File Provider mount), SHA-1 verified.

## Diff vs backup (EXCEPT, both directions), isolated == production
| Table | Diff |
|---|---|
| source_observation | 52 modified (`source_id` only) |
| evidence_amendment | +52 |
| sqlite_sequence | 1 modified (amendment counter, bookkeeping) |
| every other table, schema | 0 |

Idempotency: the second run made 0 updates and added 0 amendment rows; the content hash was unchanged. The production diff file is byte-identical to the isolated one.

## Production apply
- Pre-apply: SHA-1 `2a315b311f117844d7683f4364e1b0ad4f57802f`; `lsof` empty.
- Result: COMMITTED (52 updates); `wal_checkpoint(TRUNCATE)` returned `0|0|0`; no side files remain.
- Post-checks: `integrity_check` ok; `foreign_key_check` shows only the known 297 orphans (`field_provenance → source_observation`).
- **New production SHA-1: `df9e2d9b391aa1b50edc42e27ccd63911345adf5`.**
