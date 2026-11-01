# CarRec — standing rules for Claude Code sessions

These KB rules live in this repo-root `CLAUDE.md`. There is no `knowledge_base/CLAUDE.md`.

## Two systems, one repo
- Flask recommender (`app.py`, `services/`, `ranking_engine.py`, `ml_parser/`) reads only `car_recommendation_assets/processed_dataset.csv` + pickles. It does not touch the KB.
- Knowledge base (KB): `knowledge_base/carrec_kb.db` (SQLite, WAL mode). **Production.** Not in git (ignored), and neither are `knowledge_base/backups/` and `scratch/`. KB code (`knowledge_base/db/`, `knowledge_base/ingestion/`), reports (`knowledge_base/reports/`), `KB_SCHEMA.sql` and this file **are tracked** on `paper/v0` and the `kb/*` branches.

## Production DB — read-only by default
- Never open `knowledge_base/carrec_kb.db` for writing unless the user explicitly authorises a named controlled write in this session.
- Before any read: run `lsof knowledge_base/carrec_kb.db knowledge_base/carrec_kb.db-wal knowledge_base/carrec_kb.db-shm` and resolve each holder's full name with `lsof +c 0` or `ps -o comm= -p <PID>`; never judge by PID. A holder is allowed for a READ only if ALL of these hold:
  1. the process is `com.apple.Virtualization.VirtualMachine` (by name; macOS's virtualization service, under `/System/Library/Frameworks/Virtualization.framework/`);
  2. its FD mode is read-only (`r`; never `u` or `w`);
  3. no `-wal` and no `-shm` file exists for the DB;
  4. the `.db` SHA-1 is identical before and after you copy it.
  Anything else (another process, a `u`/`w` FD, a side file, a hash change): STOP and report the raw lsof output. (DB Browser for SQLite has held the DB open rw before. The virtualization service holds it `r` while the repo folder is shared into a VM; first seen 2026-11-02, PID 4854.)
- Before any WRITE to production: ANY holder at all, including the allowed read-only reader above, means STOP and ask the owner. Do not kill the process or work around it. Proceed only on the owner's explicit acceptance for that write.
- Record `shasum -a 1` of `.db` and `-wal` (if present). A non-empty `-wal` means the file hash does not describe the DB.
- Query a copy: `cp knowledge_base/carrec_kb.db{,-wal} /tmp/carrec_audit/prod/` (no -shm), then query the copy. Do **not** rely on `?immutable=1` when a -wal exists (it ignores WAL content). `?mode=ro` still writes -shm.
- Re-check the SHA-1 after your work; if it changed and you were not authorised to write, stop and report.
- Nearly every repo script opens the DB read-write even when it only reads. Do not run repo scripts against production; read their source instead.

## NEVER run on production
`run_mini_pilot.py`, `test_debug.py`, `orchestrator.py`, anything in `knowledge_base/ingestion/{carwale,v3cars,source_91wheels}/` batch/ingest runners, `knowledge_base/db/migrate_v6.py`, `knowledge_base/db/migrate_editions.py`, `scratch/production_ingestion*.py`, `scratch/final_production_ingestion.py`, `scratch/phase8_production_ingestion.py`, `scratch/phase8b_prod_ingestion.py`, `scratch/test_oem_override*.py`, all `fix_*`/`patch_*`/`rewrite_*`/`update_*` source rewriters, and `pytest` from the repo root (collects a test that opens prod). Full list and reasons: `knowledge_base/reports/CLAUDE_CODE_SCRIPT_SAFETY_MAP.md`.

## Controlled-write procedure (only when explicitly authorised)
1. `lsof` empty, or the owner has explicitly accepted the holder for this write (see the write rule above); record SHA-1 (+ `.sha3sum` via sqlite3).
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
- **Read path:** consumers (recommender, any KB bridge, analyses) MUST read canonical values via `v_variant_canonical_q` (quarantined cells masked to NULL) and corroboration via `v_corroboration`; statuses via `v_observation_status` / `v_safety_test_status`; safety applicability ONLY via `v_safety_applicability_q` (hides quarantined rows, rows of quarantined tests, and rows of `no_match` tests). Raw tables are allowed only for audits. Quarantine = rows in `evidence_quarantine` (never delete evidence); in-place fixes log to `evidence_amendment`.
- Safety applicability is MODEL_LEVEL / FAMILY_LEVEL with `variant_id` NULL; all 62 generations are placeholders ("Gen 1 (V6 Import)").
- Known defects: fixed or quarantined in Phase 10B W1–W6 and Phase 10E (see `knowledge_base/reports/phase10b/`, `knowledge_base/reports/phase10e/`).
  - OEM extraction spot-checked in Phase 10C-1 (closed 2026-11-02; W4 corroboration confirmed). CarWale resolver code fixed in 10C-2; before any CarWale re-ingestion a match-type signal is still required (PHASE10C2_RESOLVER_FIX.md).
  - B4 edition identity: 814 and 826 were re-based in 10E (814 → 652 ZX, 826 → 220 Alpha+). **833 is still open (high-priority backlog):** its name says "1.5L Turbo Automatic (DCT)", but it is linked to base 643 (Topline 1.0 TC) and powertrain 103 (999 cc). The Virtus brochure does not mention the edition, and it offers the 1.5 DSG only on GT Plus trims.
  - Variant ids run 1–833 for 832 rows: id **813** is a gap, not a defect. A CarWale-pilot edition was created and deleted on 2026-09-09 (the same clean-up that left the 297 orphans).
  - Still open: CATALOG_CURRENCY (no model-year dimension; Brezza, Baleno, Kylaq Sportline; see the 10D audit).

## Evidence discipline for reports
Tag claims [VERIFIED] (query/file:line/hash) · [REPORTED-ONLY] · [CONTRADICTED]. Never upgrade a prior report's claim without re-checking. Git has no KB history — use backups, hashes, mtimes, and say so.

## Where things live
- Reports: `knowledge_base/reports/` (phase reports PHASE3…PHASE9B; latest audit `CLAUDE_CODE_FULL_PROJECT_AUDIT.md`, `CLAUDE_CODE_SCRIPT_SAFETY_MAP.md`, notes in `audit_notes/`).
- Backups: `knowledge_base/backups/` (pre_phase5_carwale — MISLABELLED: already contains the 297 orphans, not a pre-CarWale state; pre_phase8/phase8b = e752ebde, phase9b = c1e0647c, pre_phase10b_w0_20260927T012954Z = pre-W0, pre_phase10b_w1_20260927T015904Z = pre-W1, pre_phase10b_w2_20260927T075058Z = pre-W2, pre_phase10b_w3_20260927T080046Z = pre-W3, pre_phase10b_w3b_20260927T080255Z = pre-W3b, pre_phase10b_w4_20260927T080859Z = pre-W4, pre_phase10b_w6_20260928T194755Z = pre-W6, pre_phase10e_20261101T231809Z = pre-10E (= 8592508); copies of the 10B backups in Google Drive My Drive/CarRec_backups/). Paper snapshot (frozen, chmod 444): `~/carrec_kb_snapshots/carrec_kb_paper_v0_8592508.db`. Current prod SHA-1: `57f31e4d4a5f1f01b4a12e1c0d2e507795953cfe` (2026-11-02, after Phase 10E) — update after every authorised controlled write.
- Schema: live `sqlite_master` is authoritative; `KB_SCHEMA.sql` is stale.
- Scratch: `/tmp/carrec_audit/` for DB copies and query output.
