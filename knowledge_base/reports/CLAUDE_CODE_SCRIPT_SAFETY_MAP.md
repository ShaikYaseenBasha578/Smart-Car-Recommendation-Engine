# CarRec — Script Safety Map (Claude Code audit, 2026-09-27)

Scope: every script that can write to `knowledge_base/carrec_kb.db` (production), its backups, or its evidence artifacts. Built from static reading only — **no script was executed**.
Tags: [VERIFIED] = I read the cited lines. [REPORTED-ONLY (subagent)] = found by a read-only subagent, not re-read by me.
Production checksum during this audit: SHA-1 `1e3eb6795452860276eca24e7dd1f52e85e67a93` (unchanged at start and end).

## Classifications
- **SAFE READ-ONLY**: opens DB only with `mode=ro`, or only reads non-DB files.
- **CONTROLLED WRITE**: writes production only after a checksum gate and with explicit transactions; still needs backup + isolated idempotency run.
- **HIGH-RISK-LEGACY**: writes/deletes production without gates, commits partially, restores files over prod, or runs outdated code paths.
- **UNKNOWN**: cannot classify (missing, or behaviour depends on untraced code).

## Cross-cutting facts
- Every DB path is **relative to the repo root** (`knowledge_base/carrec_kb.db`) except CarWale/V3Cars (`__file__`-based → still production) [VERIFIED: acquire_brochures.py:15, run_mini_pilot.py:3, test_debug.py:6, phase8b_prod_ingestion.py:4; CarWale/V3Cars `__file__` paths REPORTED-ONLY (subagent)]. Running from another cwd silently creates an empty DB.
- Only `scratch/phase7_audit.py` and `scratch/phase7a_audit.py` open with `mode=ro` [REPORTED-ONLY (subagent)]. **Every other "read-only" script opens production read-write**; in WAL mode that creates `-wal/-shm` and can checkpoint.
- No KB writer sets `PRAGMA foreign_keys=ON` (only `scratch/phase8_production_ingestion.py:51`) [VERIFIED grep].
- No script creates the backups in `knowledge_base/backups/` or performed the 09-12 restore / 09-23 Phase-8 revert — those were manual [REPORTED-ONLY (subagent) + VERIFIED absence of Phase 8 revert in reports].
- Phase 9A / 9B remediation scripts are **not on disk** — the 9B change is not reproducible from code [VERIFIED `ls scratch`].

## Table

| Script | Purpose | Classification | Production risk | Preconditions it checks | Backup required | Idempotency required |
|---|---|---|---|---|---|---|
| `run_mini_pilot.py` | CarWale mini-pilot: DELETE Harrier CarWale prov+obs, **DELETE all edition variants**, commit, re-ingest | HIGH-RISK-LEGACY | **Deletes observations/provenance/variants in prod** (L8-11) [VERIFIED]; likely contributor to the 297 orphans | none | n/a — never run | n/a |
| `test_debug.py` | Deletes one Harrier Dark Edition observation, commits, probes resolver/updater | HIGH-RISK-LEGACY | DELETE source_observation without provenance cleanup (L10-11) [VERIFIED] | none | n/a — never run | n/a |
| `orchestrator.py` | Runs CarWale batch runner after editing state JSON | HIGH-RISK-LEGACY | Full CarWale re-ingest into prod [REPORTED-ONLY (subagent)] | none | yes | yes |
| `knowledge_base/ingestion/carwale/ingest_carwale.py`, `batch_runner_carwale.py` | CarWale crawl → resolve → update | HIGH-RISK-LEGACY | Commits per variant; unresolved obs after last commit lost; resolves via 91wheels aliases; known E/EX swap and edition over-absorption [VERIFIED data] | none | yes | yes (obs dedup on source_id+url+name only) |
| `knowledge_base/ingestion/v3cars/ingest_v3cars.py`, `batch_runner_v3cars.py` | V3Cars crawl → update | HIGH-RISK-LEGACY | Absent feature → 0, status forced 'resolved' (field_map_v3cars.py:24, ingest_v3cars.py:104) [VERIFIED] | none | yes | yes |
| `knowledge_base/ingestion/source_91wheels/*` | 91wheels crawl | HIGH-RISK-LEGACY (non-runnable) | Broken imports; batch_runner commits per model to relative prod path [REPORTED-ONLY (subagent)] | none | yes | yes |
| `knowledge_base/ingestion/common/updater.py` | Canonical updater (library) | HIGH-RISK-LEGACY (library) | UPDATE variant/powertrain in place; shared powertrain updates; `updates` count bug; never deletes [VERIFIED L212-224] | caller-owned txn | caller | caller |
| `knowledge_base/ingestion/oem/batch_runner_oem.py` | OEM batch on isolated copy | CONTROLLED WRITE (to copy) | `os.remove` + copy prod → `knowledge_base/isolated_batch_kb.db`; never commits; **hard-codes source_id=1** (L141) [VERIFIED] | none | no (copy) | n/a |
| `knowledge_base/ingestion/oem/ingest_oem.py` | OEM payload → updater | HIGH-RISK-LEGACY (library) | constant url `offline_brochure` → lossy dedup (L40) [VERIFIED] | generation 0/>1 raises | caller | caller |
| `knowledge_base/ingestion/oem/acquire_brochures.py` | Manifest re-verify, quarantine moves | CONTROLLED WRITE (artifacts) | Moves PDFs to `_quarantine`; rewrites manifest; opens prod rw for SELECT [VERIFIED L15,51] | %PDF magic | copy of sources/ | — |
| `knowledge_base/ingestion/oem/test_acquire_brochures.py` | pytest | HIGH-RISK-LEGACY (test) | **pytest from repo root opens production rw** (via get_models) [VERIFIED] | none | — | — |
| `knowledge_base/db/migrate_v6.py` | Build KB from V6 CSV | HIGH-RISK-LEGACY | `os.remove(DB_PATH)` then rebuild (L85-86); path resolves to prod if file moved to its documented location [REPORTED-ONLY (subagent)] | none | yes | no |
| `knowledge_base/db/migrate_editions.py` | ALTER variant, DROP/CREATE `v_effective_variant` | HIGH-RISK-LEGACY | Schema mutation on relative prod path [REPORTED-ONLY (subagent)] | none | yes | no (ALTER fails on rerun) |
| `knowledge_base/db/validate_migration.py`, `query_demo.py`, `reports/audit_carwale_crawl.py` | Read queries | SAFE READ-ONLY *(logic)* but opens rw | rw connection only | — | — | — |
| `scratch/production_ingestion.py` | Phase-6 OEM, single txn | HIGH-RISK-LEGACY | per-model errors swallowed then COMMIT [REPORTED-ONLY (subagent)] | none | yes | yes |
| `scratch/final_production_ingestion.py` | Phase-6 OEM per-model txn | HIGH-RISK-LEGACY | no gates [REPORTED-ONLY (subagent)] | none | yes | yes |
| `scratch/production_ingestion_runner.py` | Phase-6 OEM + idempotency | HIGH-RISK-LEGACY | wrong arity call → all models fail [REPORTED-ONLY (subagent)] | none | yes | yes |
| `scratch/production_ingestion_controlled.py` | Phase-6 controlled OEM | CONTROLLED WRITE (obsolete) | **`shutil.copy2(BACKUP_DB, PROD_DB)` at L236/L338** without removing -wal/-shm [VERIFIED]; SHA-1 gate expects 6ea3b931 (now stale → would abort) | SHA-1 + integrity | yes | yes |
| `scratch/phase8_production_ingestion.py` | Phase-8 BNCAP (324 applicability) | HIGH-RISK-LEGACY | `ingest()` commits internally before invariant checks → checks cannot roll back (L62 → v4:498) [VERIFIED]; DDL autocommit | diff vs backup only | yes | yes |
| `scratch/phase8a_shadow_ingestion*.py` (v1–v4) | BNCAP shadow ingest on copies; downloads PDFs | CONTROLLED WRITE (copies) | Overwrites `bncap_raw_results.json`, PDFs; `ingest()` is imported by prod scripts [REPORTED-ONLY (subagent)] | — | — | — |
| `scratch/phase8b_prod_ingestion.py` | Phase-8B BNCAP production | CONTROLLED WRITE (obsolete) | SHA-1 gate e752ebde (now stale → aborts); DDL before BEGIN; no backup creation; no restore; hash-set diff masks modifications; removes & recreates isolated copy [VERIFIED] | SHA-1 + integrity | yes (pre-existing only) | yes |
| `scratch/check_idempotency.py`, `run_pass2.py`, `idempotency_run.py`, `integration_tests*.py`, `run_*ingestion*.py`, `run_family_validation.py`, `test_generation_ambiguity.py`, `test_phase6_blockers.py`, `test_final_audit.py`, `run_authority_matrix.py`, `phase8_shadow_ingestion.py`, `run_shadow_ingestion.py`, `strict_shadow_ingestion.py`, `audit_shadow_ingestion.py` | Copy prod → scratch DB, then write copy | CONTROLLED WRITE (copies) | Only copies; but they `os.remove` their target copies [REPORTED-ONLY (subagent)] | — | — | — |
| `scratch/ingest_aura.py`, `scratch/run_dry_run.py` | Write `knowledge_base/test_aura.db` / `isolated_batch_kb.db` | CONTROLLED WRITE (copies in KB dir) | pollutes `knowledge_base/` with DB copies | — | — | — |
| `scratch/test_oem_override*.py` | INSERT model/variant on prod, then rollback | HIGH-RISK-LEGACY | relies on rollback; rw on prod [REPORTED-ONLY (subagent)] | none | yes | — |
| `import_manual_brochures.py` | Copy PDFs from ~/Downloads into sources/, rewrite manifest | CONTROLLED WRITE (artifacts) | overwrites manifest/import_report; checks SHA-256 after copy [REPORTED-ONLY (subagent)] | sha256 | copy of sources/ | — |
| `snapshot_pre_carwale.py` | Writes carwale_snapshot_before.json | SAFE READ-ONLY *(logic)* — rw connection; **overwrites historical snapshot JSON** | — | — | — |
| `fix_*.py`, `patch_*.py`, `rewrite_*.py`, `update_updater_classification.py`, `rename_heuristics.py`, scratch `patch_*`/`rewrite_*`/`update_mappings*` | Regex-rewrite KB source files (updater, resolver, field maps, tests, reports) | HIGH-RISK-LEGACY (code) | Silently rewrite untracked source with no VCS → irreversible; several target stale layouts | none | git commit of KB code first | — |
| `forensic_*.py`, `get_recovered.py`, `query_db.py`, `integrity_check.py`, `check_integrity.py`, `evaluate_harrier.py`, `generate_*table*.py`, `trace_resolution.py`, `test_db_lookup.py`, `test_harrier_resolution.py`, many `scratch/debug_*`, `diagnose_*`, `pk_diff`, `verify_*` | Reads | SAFE READ-ONLY *(logic)* but rw connection on prod | WAL side-files; any accidental write would persist | — | — | — |
| `generate_real_table.py` | Live CarWale fetch + resolver | SAFE READ-ONLY *(logic)*, network | — | — | — | — |
| `scratch/phase7_audit.py`, `scratch/phase7a_audit.py` | Coverage audits | SAFE READ-ONLY (`mode=ro`) | none | — | — | — |
| Phase 9A / 9B scripts | Isolated test + prod remediation | UNKNOWN (missing from disk) | Cannot be re-audited | — | — | — |
| Flask app (`app.py`, `services/`, `ranking_engine.py`, `utils*.py`, `ml_parser/`) | Recommender | SAFE (no KB access) [VERIFIED grep] | none to KB | — | — | — |

## NEVER-RUN-ON-PRODUCTION
Do not execute these with cwd = repo root (or at all) while `knowledge_base/carrec_kb.db` is the production file:
1. `run_mini_pilot.py` — deletes observations, provenance and all edition variants.
2. `test_debug.py` — deletes an observation, orphans provenance.
3. `orchestrator.py`, `knowledge_base/ingestion/carwale/batch_runner_carwale.py`, `ingest_carwale.py` — unguarded prod crawl/commit.
4. `knowledge_base/ingestion/v3cars/batch_runner_v3cars.py`, `ingest_v3cars.py` — unguarded; absent→0 writes.
5. `knowledge_base/ingestion/source_91wheels/batch_runner.py` (and anything in that package).
6. `knowledge_base/db/migrate_v6.py` — deletes and rebuilds the DB.
7. `knowledge_base/db/migrate_editions.py` — schema ALTER / DROP VIEW.
8. `scratch/production_ingestion.py`, `scratch/final_production_ingestion.py`, `scratch/production_ingestion_runner.py`, `scratch/production_ingestion_controlled.py` (the last can copy an old backup over prod).
9. `scratch/phase8_production_ingestion.py`, `scratch/phase8b_prod_ingestion.py` — already applied; re-running targets a stale checksum or re-adds rows.
10. `scratch/test_oem_override.py`, `scratch/test_oem_override2.py`.
11. `pytest` collected from repo root (picks up `knowledge_base/ingestion/oem/test_acquire_brochures.py`, which opens prod rw).
12. Every `fix_*`, `patch_*`, `rewrite_*`, `update_*`, `rename_heuristics.py` (source rewriters) — until KB code is under version control.
13. Any script that does `sqlite3.connect("knowledge_base/carrec_kb.db")` without `?mode=ro` — treat as NEVER-RUN unless reviewed.

## Required procedure for any future controlled write
1. Close all DB clients (`lsof knowledge_base/carrec_kb.db*` must be empty); record SHA-1 of `.db` (+ `-wal` if present — a non-empty WAL means the file hash does not describe the DB state).
2. Backup with `sqlite3 prod ".backup 'knowledge_base/backups/<phase>_<ts>.db'"` (WAL-consistent) and verify the backup's `.sha3sum` equals prod's.
3. Run the change on an isolated copy; produce a full per-table `EXCEPT` diff both directions (not row counts, not hash-set heuristics).
4. Re-run on the post-change copy → must produce an empty diff (idempotency).
5. Apply to prod in one explicit transaction with `PRAGMA foreign_keys=ON`; invariant checks **before** COMMIT.
6. Post: `integrity_check`, `foreign_key_check` (only the known 297 allowed), diff vs backup equals the isolated diff, `PRAGMA wal_checkpoint(TRUNCATE)`, record new SHA-1, and commit the script + report to git.
