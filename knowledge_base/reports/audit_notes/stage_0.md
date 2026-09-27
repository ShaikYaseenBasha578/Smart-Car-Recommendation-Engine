# Stage 0 — Baseline (2026-09-27)

## Pre-audit observation (plan mode, before any copy)
- [VERIFIED] `lsof knowledge_base/carrec_kb.db*` showed **DB Browser for SQLite (PID 30936)** holding `carrec_kb.db` (fd 30u, read-write), `-wal` (33u), `-shm` (34u).
- [VERIFIED] At that moment: `carrec_kb.db` SHA-1 `1e3eb6795452860276eca24e7dd1f52e85e67a93`; `-wal` 24,752 B SHA-1 `ba0f15d1…c8a6` (32-B header + 6×4120-B frames); `-shm` 32,768 B SHA-1 `18678203…ebec`. mtimes: db 09-26 03:31, wal 09-26 03:30, shm 09-26 03:53.
- User closed DB Browser (instructed: without "Write Changes").

## Stage 0 proper
- [VERIFIED] `lsof` → no handles (rc=1).
- [VERIFIED] `-wal` and `-shm` no longer exist; `carrec_kb.db` SHA-1 still `1e3eb6795452860276eca24e7dd1f52e85e67a93`, size 38,436,864, mtime 09-26 03:31. ⇒ The 6 WAL frames were either already checkpointed into the main file or were uncommitted and discarded; either way the main file bytes did not change. **Stage-0 reference checksum = `1e3eb6795452860276eca24e7dd1f52e85e67a93`** (matches claimed post-9B value).
- [VERIFIED] Snapshot copied to `/tmp/carrec_audit/prod/carrec_kb.db` (identical SHA-1). All queries below on the copy.
- [VERIFIED] `PRAGMA journal_mode` = `wal` (persistent header setting). Any process opening production in rw mode will create `-wal/-shm` again.
- [VERIFIED] `.sha3sum` of `immutable=1` production open == `.sha3sum` of copy: `fd3cd81b310608f592f51712c1e929cf675d42459df7f4ac6d2a8585`.
- [VERIFIED] `PRAGMA integrity_check` → `ok`.
- [VERIFIED] `PRAGMA foreign_key_check` → **297 rows, all `field_provenance → source_observation`** (rowids 31888…); no other table has FK violations. Matches the 297 orphan claim [REPORTED-ONLY → count VERIFIED; cause verified in later stage].

## Backups (hash only; queried via copies later)
| file | size | mtime | SHA-1 |
|---|---|---|---|
| backups/carrec_kb_pre_phase5_carwale.sqlite | 30,236,672 | 09-09 20:54 | f604994b466dffda9a31a865b6160ea8429296ee |
| backups/carrec_kb_pre_phase8_20260923210209.db (+0-B wal, 32 KB shm) | 38,232,064 | 09-23 21:02 | e752ebde5b7f227140bedb319c6b9753a3fdbdde |
| backups/carrec_kb_phase8b_backup.db | 38,232,064 | 09-23 21:33 | e752ebde… (identical to pre_phase8) |
| backups/carrec_kb_phase9b_backup.db | 38,436,864 | 09-26 03:30 | c1e0647ce463c98eebd9d2bd9470940fdb23ead5 (= claimed pre-9B) |

## Git
- Repo root: `Flask Based App with Used Cars Function/`; branch `codex/small-hybrid-refresh`; 14 commits total (`git log --oneline -50` returns 14). Latest `06ba1b5`.
- [VERIFIED] `git status --short`: 200 lines = 97 `??`, 97 ` D`, 6 ` M` (saved `/tmp/carrec_audit/git_status_start.txt`).
  - ` D` (tracked, deleted from working tree): `README.md`, `datasets/{final(14),processed(6),research(21)}`, **entire `scraping/` package (55 files incl. tests)**.
  - ` M`: `static/script.js`, `static/style.css`, `templates/{index,recommend,used}.html`, `utils_used.py`.
- [VERIFIED] `git ls-files knowledge_base scratch` → **0 files**. `knowledge_base/` and `scratch/` are wholly untracked (`??`).
- [VERIFIED] `git check-ignore -v knowledge_base/*`:
  - `knowledge_base/.gitignore:1:carrec_kb.db` → `knowledge_base/carrec_kb.db`
  - `.gitignore:221:**/__pycache__/` → `knowledge_base/__pycache__`
- [VERIFIED] `git status --ignored` (KB-relevant `!!`): `knowledge_base/carrec_kb.db`, `knowledge_base/ingestion/carrec_kb.db` (0-byte stray), `knowledge_base/sources/oem/tata/punch/` (ignored dir), `scratch/*.log` (14 logs), `__pycache__` dirs, `.DS_Store`s. Everything else under `knowledge_base/` (reports, ingestion code, tests, backups, sources PDFs) and all ~60 root `fix_*/patch_*/rewrite_*/forensic_*` scripts are **untracked, not ignored**.
- Consequence: **no KB code, schema, report, or DB history exists in git.** All KB history in this audit comes from reports [REPORTED-ONLY] and file mtimes/hashes [VERIFIED (mtime)]; causal attributions are inferences.

## Prior-agent artifacts
- `../AGENTS.md` ("Ponytail" lazy-senior-dev rules), `../.agents/` and `./.agents/{rules,workflows}/graphify.md` (consult `graphify-out/` graph; run `graphify update .` after code edits), `.agent/skills/impeccable` and `.gemini/skills/impeccable` (UI-design skill, node scripts), `.impeccable/config.json`, `knowledge_base/reports/AGENTS.md` (read in Stage 1).

## Checksum gate
- End of stage 0: `1e3eb6795452860276eca24e7dd1f52e85e67a93` ✔
