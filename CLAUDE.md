# CarRec — standing rules for Claude Code sessions

## Two systems, one repo
- Flask recommender (`app.py`, `services/`, `ranking_engine.py`, `ml_parser/`) reads only `car_recommendation_assets/processed_dataset.csv` + pickles. It does not touch the KB.
- Knowledge base (KB): `knowledge_base/carrec_kb.db` (SQLite, WAL mode). **Production.** Not in git (ignored); KB code, reports, backups and `scratch/` are untracked.

## Production DB — read-only by default
- Never open `knowledge_base/carrec_kb.db` for writing unless the user explicitly authorises a named controlled write in this session.
- Before any read: `lsof knowledge_base/carrec_kb.db*` must be empty (DB Browser for SQLite has held it open rw before).
- Record `shasum -a 1` of `.db` and `-wal` (if present). A non-empty `-wal` means the file hash does not describe the DB.
- Query a copy: `cp knowledge_base/carrec_kb.db{,-wal} /tmp/carrec_audit/prod/` (no -shm), then query the copy. Do **not** rely on `?immutable=1` when a -wal exists (it ignores WAL content). `?mode=ro` still writes -shm.
- Re-check the SHA-1 after your work; if it changed and you were not authorised to write, stop and report.
- Nearly every repo script opens the DB read-write even when it only reads. Do not run repo scripts against production; read their source instead.

## NEVER run on production
`run_mini_pilot.py`, `test_debug.py`, `orchestrator.py`, anything in `knowledge_base/ingestion/{carwale,v3cars,source_91wheels}/` batch/ingest runners, `knowledge_base/db/migrate_v6.py`, `knowledge_base/db/migrate_editions.py`, `scratch/production_ingestion*.py`, `scratch/final_production_ingestion.py`, `scratch/phase8_production_ingestion.py`, `scratch/phase8b_prod_ingestion.py`, `scratch/test_oem_override*.py`, all `fix_*`/`patch_*`/`rewrite_*`/`update_*` source rewriters, and `pytest` from the repo root (collects a test that opens prod). Full list and reasons: `knowledge_base/reports/CLAUDE_CODE_SCRIPT_SAFETY_MAP.md`.

## Controlled-write procedure (only when explicitly authorised)
1. `lsof` empty; record SHA-1 (+ `.sha3sum` via sqlite3).
2. Backup with `sqlite3 prod ".backup 'knowledge_base/backups/<phase>_<UTCts>.db'"`; verify backup `.sha3sum` == prod.
3. Apply to an isolated copy; produce a full per-table `EXCEPT` diff in both directions (not counts, not hash-set heuristics).
4. Re-apply on the post-change copy → diff must be empty (idempotency).
5. Apply to prod in ONE explicit transaction with `PRAGMA foreign_keys=ON`; invariant checks **before** COMMIT; no DDL outside the transaction.
6. After: `integrity_check`; `foreign_key_check` (only the known 297 `field_provenance` orphans allowed); diff vs backup == isolated diff; `PRAGMA wal_checkpoint(TRUNCATE)`; record new SHA-1.
7. Save the exact script and report in the repo and commit them on a `kb/*` branch (Phase 9A/9B scripts were lost — don't repeat that).

## Do not touch casually
The 297 orphaned `field_provenance` rows (keep, never re-point); the 24 Global NCAP rows in `safety_rating` (no migration without protocol handling); `scratch/bncap_pdfs/*` (SHA-256 pinned in `safety_test.artifact_checksum`); `knowledge_base/sources/oem/*`; `knowledge_base/backups/*`; `scratch/carrec_kb_idemp.db` (only copy of the reverted Phase 8 state); `source` ids; `authority_matrix.py` tiers; resolver thresholds.

## Data principles
- PRECISION > COVERAGE. Ambiguous evidence stays NULL / UNRESOLVED / NO_MATCH. Never infer variant-level facts from model-level evidence. "Not mentioned" is unknown, never 0.
- Keep evidence classes separate: OEM_FACT (canonical columns + field_provenance) · SAFETY_TEST_RESULT (`safety_test` + applicability, never variant columns) · PROFESSIONAL_ASSESSMENT · OWNER_REPORT · DERIVED_VALUE (views/recommender only, never written back).
- Safety applicability is MODEL_LEVEL / FAMILY_LEVEL with `variant_id` NULL; all 62 generations are placeholders ("Gen 1 (V6 Import)").
- Known live defects (don't build on them): OEM observations stored under source_id 1 (v6_migration) instead of 6; BNCAP test 27 (Harrier.EV) mapped to ICE-only Harrier; V3Cars absent→0 facts; CarWale E/EX swap and edition over-absorption; 3 BNCAP observation statuses stale after 9B.

## Evidence discipline for reports
Tag claims [VERIFIED] (query/file:line/hash) · [REPORTED-ONLY] · [CONTRADICTED]. Never upgrade a prior report's claim without re-checking. Git has no KB history — use backups, hashes, mtimes, and say so.

## Where things live
- Reports: `knowledge_base/reports/` (phase reports PHASE3…PHASE9B; latest audit `CLAUDE_CODE_FULL_PROJECT_AUDIT.md`, `CLAUDE_CODE_SCRIPT_SAFETY_MAP.md`, notes in `audit_notes/`).
- Backups: `knowledge_base/backups/` (pre_phase5_carwale — MISLABELLED: already contains the 297 orphans, not a pre-CarWale state; pre_phase8/phase8b = e752ebde, phase9b = c1e0647c). Current prod SHA-1: `1e3eb6795452860276eca24e7dd1f52e85e67a93` (2026-09-27) — update after every authorised controlled write.
- Schema: live `sqlite_master` is authoritative; `KB_SCHEMA.sql` is stale.
- Scratch: `/tmp/carrec_audit/` for DB copies and query output.
