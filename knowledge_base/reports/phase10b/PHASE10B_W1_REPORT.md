# Phase 10B W1: B3 CarWale quarantine (controlled write)

**Date:** 2026-09-27. **Branch:** kb/phase-10-0-versioning.
**Design:** PHASE10B0_QUARANTINE_DESIGN.md. **Scope:** PHASE10A_BUG_IMPACT.md B3, as approved (347 entries).
**Operation:** inserts into `evidence_quarantine` only. **No existing row was updated or deleted.**

## Artifacts
- **Entry list:** `knowledge_base/db/migrations/phase10b_w1_entries.csv` (347 rows), derived from `reports/phase10a/B3_affected.csv`. Each `note` holds the 10A tags, resolved variant, and provenance id.
- **Applier:** `knowledge_base/db/migrations/apply_phase10b_w1.py`.
  - Runs as one `BEGIN IMMEDIATE` transaction with `foreign_keys=ON`.
  - Skips an entry if an identical active entry already exists, which makes re-runs idempotent.
  - Checks invariants before `COMMIT`: only `evidence_quarantine` may change, active W1 entries must equal 347, every target must exist, and `integrity_check` must pass.
- **Backup:** `knowledge_base/backups/pre_phase10b_w1_20260927T015904Z.db`.
  - File SHA-1: `72f642c05f5a282d007b5464403c98fa47e4e96b`.
  - Content `.sha3sum`: `0e79cf63…afb81d9`, which equals production before W1 (post-W0).

## Entries (phase `10B-W1`)
| reason_code | target | count |
|---|---|---|
| `B3_CARWALE_STRUCTURAL_MISMATCH` | source_observation | 331 (329 fuel/transmission conflicts, plus 3185 and 3187 on variant 820; see below) |
| `B3_CARWALE_SWAP` | source_observation | 2 (obs 2842 and 2843; quarantined only, not re-linked) |
| `B3_SOLE_SOURCE_FROM_MISRESOLVED` | variant cell | 14 cells on 12 variants |

The 264 name-only mismatches (`B3_loose_name_mismatch_UNDETERMINABLE.csv`) are not in scope.

## Diff vs backup (EXCEPT, both directions)
| Table | Isolated | Production |
|---|---|---|
| evidence_quarantine | +347 / −0 | +347 / −0 |
| sqlite_sequence | +1 (AUTOINCREMENT counter row for `evidence_quarantine`; SQLite bookkeeping) | +1 |
| all 14 data tables, evidence_amendment | 0 / 0 | 0 / 0 |
| schema objects | none added, removed or changed | same |

- The production diff file is byte-identical to the isolated one.
- **Idempotency:** the second run inserted 0 rows and the content `.sha3sum` was unchanged.
- Production's content hash (`76313d5c…`) differs from the isolated copy's only because of the `created_at` timestamps.

## Production apply
- **Before:** `lsof` was empty and SHA-1 was `2c04286ac891f85db549cfe73125bd639e06f16c`.
- **Applier result:** COMMITTED (inserted 347). `wal_checkpoint(TRUNCATE)` returned `0|0|0`, no side files remain, and `lsof` is empty.
- **Post-checks, on a /tmp copy:**
  - `integrity_check` is ok.
  - `foreign_key_check` returns 297 rows, all the known `field_provenance → source_observation` orphans.
- **New production SHA-1:** `6f35aa422e290fe7872c84bfb6e080e8584021b1`.

## View effects
| View | Before W1 | After W1 |
|---|---|---|
| v_active_quarantine | 0 | 347 |
| v_live_evidence | 36,148 | 34,059 (−2,089, exactly the provenance of the 333 observations) |
| v_corroboration | 26,010 | 25,971 |
| v_variant_canonical_q vs v_effective_variant | identical | 12 variant rows differ (14 masked cells); no edition inherits a masked base cell |

## Observation 3185: a probable false positive (still quarantined, per owner decision)
**Why it was flagged.** 10A B3 included every CarWale observation resolved to variant 820 (tag `ON_VARIANT_820`), because 820 absorbed 33 configurations. Observation 3185 has no fuel or transmission conflict. It was included only because of that tag.

**Why it is probably correct:**
- Its `raw_name`, "AX7 2WD Petrol 2.0L Turbo Manual 7 STR Dual Tone", equals variant 820's name exactly.
- It was observed at 2026-09-09 15:34:51, the same second variant 820 was created. That points to 3185 being the observation that created the edition.
- Its sole-source cell, 820/sunroof = 0 (fp 34390), is therefore probably legitimate. The DB cannot tell whether sunroof = 0 is *true*.

**Could the same pattern produce other false positives?** I classified all 333 entries on production data:

| Class | Count | Assessment |
|---|---|---|
| Exact normalised name match with the resolved variant (the 3185 pattern) | **1** (3185 only) | Probable false positive |
| Raw name and variant *name* disagree on fuel or transmission | 309 | Genuine mis-resolution |
| Variant name says nothing about fuel/transmission; the conflict is only with the variant's canonical fuel (powertrain) or `transmission` column (e.g. 3464 "Pure Petrol 1.2L Automatic (AMT)" → 320 "Pure", Manual) | 16 | Probably genuine; correctness depends on the canonical columns |
| Names agree on the explicit tokens, but the raw name says CNG while the variant's powertrain is Petrol (e.g. 3230 "Delta CNG Manual" → 247 "Delta MT") | 4 | Probably genuine (CNG observation bound to a petrol variant) |
| Creta E/EX swap (2842, 2843) | 2 | Genuine |
| 3187 "AX7 … 7 STR" (not Dual Tone) → 820 "… Dual Tone" | 1 | Genuine (base config bound to the edition) |

- The exact 3185 pattern occurs once.
- The 20 column-only conflicts are the only other checkable group whose correctness depends on canonical data, not on names. They would become false positives only if those variants' canonical fuel or transmission is wrong, which the DB cannot settle.
- Releasing any of them is a later, separate controlled write.

## Post-W1 B1 recomputation (read-only, on a /tmp copy of post-W1 production)
`B1_reclassified_post_w1.csv` reclassifies the 410 B1 zeros using `v_live_evidence`, which now excludes W1-quarantined CarWale evidence and orphans. Evidence must come from another source, and other B1 zero rows do not count as corroboration.

| Class | 10A | Post-W1 |
|---|---|---|
| SOLE-SOURCE | 279 | **290** |
| CORROBORATED | 104 | **100** |
| CONTRADICTED | 27 | **20** |

- **13 zeros changed class because W1 removed their evidence:**
  - CORROBORATED → SOLE-SOURCE: 6
  - CONTRADICTED → SOLE-SOURCE: 5
  - CONTRADICTED → CORROBORATED: 2
- **Exact W2 entry count under the design rule** (SOLE-SOURCE + CONTRADICTED): **310** distinct variant cells. None of them overlaps a W1-masked cell.
- **Sensitivity check.** If V3Cars zeros are excluded as corroboration *in any decision*, not only its accepted B1 rows (V3Cars writes absence as 0 for every row), then 27 more CORROBORATED zeros become SOLE-SOURCE and W2 is **337**. That matches the design's upper bound. **The owner should choose which rule W2 uses.**
- W2 has not started.
