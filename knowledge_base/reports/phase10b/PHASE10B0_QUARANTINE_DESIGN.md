# Phase 10B-0: Quarantine and Review-State Design (design only)

**Date:** 2026-09-27
**Branch:** kb/phase-10-0-versioning
**Inputs:** PHASE10A_BUG_IMPACT.md (commit 900cbb1) and CLAUDE.md.
**Production DB:** `knowledge_base/carrec_kb.db`, SHA-1 `1e3eb6795452860276eca24e7dd1f52e85e67a93` at start and at end. `lsof` was empty.
**Where the numbers come from:** all counts were queried on `/tmp/carrec_audit/p10b0/carrec_kb.db`, a byte-identical copy of production. **This phase wrote no data and changed no schema. Every SQL statement in this doc is a proposal and was not executed.**

---

## 1. Status vocabulary inventory [VERIFIED on copy]

### 1.1 `source_observation.resolution_status`
9 distinct strings, mixing uppercase and lowercase.

| Value | Source | Rows | Writer (file:line) | Meaning, from the writing code |
|---|---|---|---|---|
| applied | v6_migration | 812 | `db/migrate_v6.py:320` | Bootstrap row, bound to its variant by construction |
| resolved | v6_migration (OEM, mis-sourced) | 52 | `oem/ingest_oem.py` → `updater.py:39` | Resolver matched the variant |
| resolved | 91wheels | 457 | resolver → updater | Matched to a variant; alias verified or fuzzy/exact match |
| resolved_with_warning | 91wheels | 254 | `common/resolver.py:139,142-143` | Matched through an alias that `needs_review` or has structural warnings |
| unresolved | 91wheels | 134 | resolver return value | No match, or a tie inside the 0.05 margin |
| resolved | carwale | 753 | `carwale/ingest_carwale.py` (resolver status passed through) | Matched, but see 10A B3: 333 of these are structurally wrong |
| unresolvable | carwale | 107 | `carwale/ingest_carwale.py:96` | Resolver returned no variant |
| resolved | v3cars | 438 | `v3cars/ingest_v3cars.py:104` | **Forced** to `resolved` whatever the resolver returned (a warning is not preserved) |
| unresolvable | v3cars | 363 | `v3cars/ingest_v3cars.py:85,96` | No variant (or no model) |
| model_level | v3cars | 44 | `v3cars/ingest_v3cars.py:49-52` (direct INSERT) | Model-scope observation (warranty) |
| RESOLVED | bharat_ncap | 20 | `scratch/phase8a_shadow_ingestion_v*.py` / `phase8b_prod_ingestion.py` | Test mapped at model or family scope |
| UNRESOLVED | bharat_ncap | 7 | same | Ambiguous title, or manufacturer not identified. 3 of these are stale since 9B (B6) |
| NO_MATCH | bharat_ncap | 10 | same | The model is not among CarRec's 62 models |

### 1.2 Other tables

| Table and column | Distinct values | Counts |
|---|---|---|
| `safety_test.resolution_status` | 3 | RESOLVED 23, UNRESOLVED 4, NO_MATCH 10 |
| `field_provenance.decision` | 3 | accepted 25,593 · confirmed 8,398 · rejected 2,454 |
| `field_provenance.decision_reason` | 7 | v6_migration 24,955 · agrees_with_canonical 8,398 · conflict_with_canonical_authority 2,426 (an old updater version; `fix_updater_inheritance.py:53`) · new_field 599 · edition_override_or_correction 39 · conflict_field_tier_5_vs_best_5 26 · conflict_field_tier_5_vs_best_3 2 |
| `safety_test_applicability.match_confidence` | 2 | MODEL_LEVEL 22, FAMILY_LEVEL 1 |
| `variant.edition_classification` | 2 + NULL | NULL 812 · FEATURE_OR_SPEC_DIFFERENCE 16 · NO_MATERIAL_DIFFERENCE 4 |
| `variant_alias` (needs_review / is_verified) | — | fuzzy 0/0 280 · fuzzy 1/0 189 |
| `generation.verification_status` | 1 | unverified 62 |

**Vocabulary size today:** 9 distinct resolution strings across `source_observation` and `safety_test` combined (resolved, resolved_with_warning, unresolved, unresolvable, model_level, applied, RESOLVED, UNRESOLVED, NO_MATCH).

### 1.3 Proposed canonical resolution vocabulary: 5 values, lowercase, shared by `source_observation` and `safety_test`

| Canonical value | Definition | Maps from |
|---|---|---|
| `resolved_variant` | Bound to exactly one variant with no known warning | applied (v6), resolved (91wheels, carwale, OEM) |
| `resolved_variant_unverified` | Bound to a variant, but the binding was not structurally confirmed | resolved_with_warning; resolved (v3cars, because the status was forced) |
| `resolved_model` | Applies at model or family scope, with no variant binding | model_level; RESOLVED (BNCAP) |
| `unresolved` | The entity may exist in the KB, but the evidence is ambiguous or insufficient | unresolved; unresolvable; UNRESOLVED |
| `no_match` | The entity is not in the KB's scope | NO_MATCH |

- **Quarantine is not a resolution status.** It is an overlay (see §2). Keeping the two separate stops "we doubt this row" from overwriting "what the resolver concluded".
- **The mapping is not applied to rows.** It would be exposed through a view such as `v_observation_status` with a `CASE` expression. The historical strings stay byte-identical.
- `decision` keeps its 3 values. The 7 historical `decision_reason` strings are kept as they are and documented; new writes use a closed list.
- `match_confidence` keeps MODEL_LEVEL, FAMILY_LEVEL and a reserved VARIANT_LEVEL (uppercase, as a separate enum).

---

## 2. Quarantine representation: A vs B

**(A) New columns on existing tables.** Examples:
- `source_observation.quarantine_reason` / `quarantined_at`
- `field_provenance.quarantine_reason`
- `variant.<field>_quarantined`, or a JSON column

**(B) An additive table.** `evidence_quarantine(id, target_table, target_id, target_field NULL, reason_code, phase, note, created_at, released_at NULL, released_reason NULL)`, plus views that exclude active quarantine. It comes with a companion `evidence_amendment` log (§3.2) for the few in-place updates that remain unavoidable.

| Criterion | (A) Columns | (B) Additive table + views |
|---|---|---|
| **Reversibility** | Releasing a quarantine means a new UPDATE, and the history of that release is lost unless extra columns are added | Releasing means setting `released_at`, and the full history is kept. Rolling back the migration is `DROP TABLE` / `DROP VIEW` |
| **Provenance preservation** | Evidence rows change: their bytes and hashes differ, and quarantine state mixes with fact state | Evidence rows are never touched. Quarantine is a separate, dated, attributable assertion *about* the evidence |
| **Migration risk** | `ALTER TABLE` on 4 tables. There are many canonical columns on `variant`, and per-cell quarantine needs 30+ columns or a JSON column. Existing scripts that `SELECT *` or copy rows change behaviour | One `CREATE TABLE` and a few `CREATE VIEW`s. Existing tables and scripts are unaffected |
| **Query impact** | Every consumer must remember `WHERE quarantine_reason IS NULL`, and forgetting it silently includes bad data | Consumers read views (`v_live_evidence`, `v_variant_canonical_q`). The base tables are the raw ledger. Views add a NOT EXISTS lookup; the table is indexed on (target_table, target_id) |
| **Reads in a methodology section as** | "We annotated rows in place" — hard to show that nothing else changed | "The evidence ledger is append-only. Data-quality judgements are recorded as separate, time-stamped quarantine assertions with reason codes, and analytic views exclude active quarantines." This is auditable and reproducible from the commits plus the table |
| **Per-cell granularity** (needed by B1) | Awkward | Native, via `target_field` |

**Recommendation: (B).** It is the only option that keeps evidence rows byte-identical, supports per-cell quarantine, and can be reversed by deleting the added objects. It also matches the project's PRECISION > COVERAGE, append-only-evidence stance.

### 2.1 Proposed DDL (not executed)
```sql
CREATE TABLE evidence_quarantine (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  target_table  TEXT NOT NULL CHECK (target_table IN
                 ('source_observation','field_provenance','variant','safety_test','safety_test_applicability')),
  target_id     INTEGER NOT NULL,
  target_field  TEXT,                       -- required when target_table='variant' (cell-level)
  reason_code   TEXT NOT NULL,              -- closed list, §3
  phase         TEXT NOT NULL,              -- e.g. '10B-1'
  note          TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  released_at   TEXT,
  released_reason TEXT,
  CHECK (target_table <> 'variant' OR target_field IS NOT NULL)
);
CREATE UNIQUE INDEX ux_quarantine_active
  ON evidence_quarantine(target_table, target_id, IFNULL(target_field,''), reason_code)
  WHERE released_at IS NULL;

CREATE TABLE evidence_amendment (          -- log of every in-place UPDATE a fix performs
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_table TEXT NOT NULL, target_id INTEGER NOT NULL, column_name TEXT NOT NULL,
  old_value TEXT, new_value TEXT, reason_code TEXT NOT NULL, phase TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

---

## 3. Reason codes and rules

### 3.1 Reason codes (closed list)

| Code | Target | Used by | Meaning |
|---|---|---|---|
| `B3_CARWALE_STRUCTURAL_MISMATCH` | source_observation | B3 | The observation's own fuel or transmission contradicts the variant it resolved to |
| `B3_CARWALE_SWAP` | source_observation | B3 | The Creta E/EX pair, obs 2842/2843 |
| `B3_SOLE_SOURCE_FROM_MISRESOLVED` | variant cell | B3 | The canonical value is supported only by quarantined observations |
| `B1_ABSENT_AS_ZERO_SOLE` | variant cell | B1 | A 0 written from "not mentioned", with no independent live corroboration |
| `B1_ABSENT_AS_ZERO_CONTRADICTED` | variant cell | B1 | A 0 written from "not mentioned" while another live source says non-zero |
| `B4_EDITION_IDENTITY_REVIEW` | variant (whole row, `target_field='*'`) | B4 | Edition name, base, powertrain or transmission is inconsistent; held for human review |
| `B5_WRONG_POWERTRAIN_SCOPE` | safety_test_applicability | B5 | An EV test is mapped to an ICE-only model |
| `B2_OEM_EXTRACTION_REVIEW` | source_observation | B2 (optional; see open questions) | OEM brochure extraction whose column alignment is unverified |

### 3.2 Rules
1. **No evidence row is ever deleted.** This covers `source_observation`, `field_provenance`, `safety_test`, `safety_test_applicability`, `variant`, and the 297 historical orphans.
2. Every in-place UPDATE a fix performs (status sync, source re-attribution) writes one `evidence_amendment` row holding the old and new values, in the same transaction.
3. **B5 uses a status change plus a quarantine entry, never a DELETE.**
   - `safety_test` 27 → NO_MATCH, and observation 3747 → NO_MATCH, each amendment-logged.
   - Applicability row 14 → quarantined with `B5_WRONG_POWERTRAIN_SCOPE`.
4. Quarantined canonical cells are **masked** in `v_variant_canonical_q`, where they read as NULL. The base `variant` table is **not** updated.
5. Quarantines are released only by setting `released_at` and `released_reason`, and that release is its own controlled write.

---

## 4. Corroboration after quarantine (view SQL, not executed)
**Corroboration count** for (variant, field) is the number of **distinct sources** with at least one **live, non-quarantined** provenance row that `accepted` or `confirmed` the value. Four things are excluded:
- orphaned provenance, meaning its observation no longer exists (the 297);
- provenance whose observation is quarantined;
- provenance rows that are themselves quarantined;
- cells whose canonical value is quarantined, which count as 0.
```sql
CREATE VIEW v_active_quarantine AS
  SELECT target_table, target_id, target_field, reason_code
  FROM evidence_quarantine WHERE released_at IS NULL;

CREATE VIEW v_live_evidence AS
  SELECT fp.id AS fp_id, fp.variant_id, fp.field_name, fp.decision, fp.accepted_value,
         so.id AS observation_id, so.source_id
  FROM field_provenance fp
  JOIN source_observation so ON so.id = fp.source_observation_id          -- drops orphans
  WHERE NOT EXISTS (SELECT 1 FROM v_active_quarantine q
                    WHERE q.target_table='source_observation' AND q.target_id=so.id)
    AND NOT EXISTS (SELECT 1 FROM v_active_quarantine q
                    WHERE q.target_table='field_provenance' AND q.target_id=fp.id);

CREATE VIEW v_corroboration AS
  SELECT e.variant_id, e.field_name,
         COUNT(DISTINCT e.source_id) AS corroborating_sources,
         GROUP_CONCAT(DISTINCT e.source_id) AS source_ids
  FROM v_live_evidence e
  WHERE e.decision IN ('accepted','confirmed')
    AND NOT EXISTS (SELECT 1 FROM v_active_quarantine q
                    WHERE q.target_table='variant' AND q.target_id=e.variant_id
                      AND (q.target_field=e.field_name OR q.target_field='*'))
  GROUP BY e.variant_id, e.field_name;
```
**Known limitation.** A `confirmed` row means the value agreed with canonical *at decision time*. If a value is later overwritten, older confirmations can be stale. The 10B writes add no overwrites, so the limitation is unchanged; a value-matching variant is future work.

`v_variant_canonical_q` has the same columns as `v_effective_variant`. Each masked column is `CASE WHEN EXISTS(active quarantine on (variant, field or '*')) THEN NULL ELSE col END`. The view is generated from `PRAGMA table_info(variant)` at migration time.

---

## 5. 10B execution sequence: separate controlled writes
Every write follows the full CLAUDE.md procedure:
- lsof, SHA-1 and `.backup` first;
- apply to an isolated copy, run the EXCEPT diff, then an idempotency re-run;
- apply to production in one transaction with `foreign_keys=ON`;
- post-checks, then record the new SHA-1 in CLAUDE.md.

The expected diffs below come from 10A. All other tables must show 0 changes.

| # | Write | Expected per-table diff |
|---|---|---|
| **W0** | Schema migration only | +2 tables (`evidence_quarantine`, `evidence_amendment`) and +5 views (`v_active_quarantine`, `v_live_evidence`, `v_corroboration`, `v_variant_canonical_q`, `v_observation_status`). **0 rows** in any existing table |
| **W1** | B3 quarantine | `evidence_quarantine` +333 (source_observation: 331 `B3_CARWALE_STRUCTURAL_MISMATCH` and 2 `B3_CARWALE_SWAP`; the 33 on variant 820 are inside these), plus **14** variant cells `B3_SOLE_SOURCE_FROM_MISRESOLVED`, for **+347**. `variant`, `field_provenance` and `source_observation`: 0 |
| **W2** | B1 quarantine | `evidence_quarantine` +306 as a floor (279 SOLE + 27 CONTRADICTED), rising to at most **+337**. The extra 31 are the 6 CORROBORATED cells that rely only on B3 evidence, plus up to 25 91wheels cells corroborated only by V3Cars zeros. The exact number is computed at dry-run from `v_corroboration` *after* W1, excluding other B1 rows. 0 changes to other tables |
| **W3** | B5 + B6 (one BNCAP transaction) | `safety_test` ~1 (id 27 → NO_MATCH). `source_observation` ~4 (3747 → NO_MATCH; 3729, 3736, 3737 → RESOLVED). `evidence_quarantine` +1 (applicability 14). `evidence_amendment` +5. `safety_test_applicability`: 0 rows deleted |
| **W4** | B2 re-attribute only | `source_observation` ~52 (`source_id` 1→6 for ids 3669–3720). `evidence_amendment` +52. `field_provenance`: 0. `variant`: 0. **No re-evaluation of tiers.** |
| **W5** | B4 | **Held for human review.** No write until the correct base, powertrain and transmission for variants 833, 814 and 826 are confirmed externally. The proposed interim is +3 `evidence_quarantine` (`B4_EDITION_IDENTITY_REVIEW`, `target_field='*'`) |

Each write's isolated-copy diff must equal its row of this table exactly. Any deviation aborts the write.

---

## 6. Separate code fix: CarWale resolver root cause (design only)
**Gate: no CarWale re-ingestion (and no release of B3 quarantines) until this fix is merged and tested.**

**The defect**, from 10A B3 and the audit:
1. `ingest_carwale.py` passes `fuel=None` and `cc=None`; `specs_summary` is never populated.
2. `validate_structured` (`resolver.py:59-75`) checks each attribute only when both sides are non-null, so the missing source values make it skip every check.
3. With no `source_name`, the alias lookup defaults to the 91wheels alias table (`resolver.py:124-129`).

Together, a slug that matches through another source's alias binds to a variant of the wrong fuel or transmission.

**Proposed changes:**
1. **Extract structure deterministically.** Parse fuel (petrol, diesel, CNG, electric/kWh, hybrid) and transmission class (manual vs automatic, from MT/AMT/DCT/CVT/IVT/TC/Automatic) from the CarWale version name. Also parse the spec block when present. Pass them to `resolve_variant`.
2. **Fail closed on unknown structure.** When the source fuel or transmission is unknown, a match may return at most `resolved_variant_unverified`, and the updater must neither accept nor confirm from it.
3. **Use per-source aliases only.** Pass `source_name='carwale'` and remove the implicit 91wheels default for other sources. A missing alias falls through to scored matching with structural validation.
4. **Treat contradiction as rejection.** If the source says Diesel/AT and the candidate is Petrol/MT, the candidate is rejected even when the alias is verified.
5. **Tests (required):**
   - a fixture built from the 331 B3 structural cases, asserting that none resolves to a contradicting variant;
   - the Creta E/EX pair resolving to the correct variant, or failing to `unresolved`;
   - regression tests on the 424 currently consistent resolutions.

   All run on in-memory DBs built from `knowledge_base/schema/live_schema.sql`.
6. **Deliverable:** a code change on a `kb/*` branch with tests, and no DB write. Re-ingestion is a later, separately gated phase.

---

## Open questions for the owner
1. Should the 4 BNCAP UNRESOLVED tests whose manufacturer isn't in the KB (Citroen ×2, VinFast ×2) map to `no_match` rather than `unresolved` in the canonical vocabulary?
2. W4: should the 52 OEM observations also get the `B2_OEM_EXTRACTION_REVIEW` quarantine? That would exclude their 104 confirmations from corroboration.
3. Should `v_variant_canonical_q` become the only interface any future recommender or KB bridge is allowed to read?
