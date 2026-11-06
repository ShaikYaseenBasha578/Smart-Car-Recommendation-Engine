# Phase 10I-1c — resolver fix (code only)

Date: 2026-11-06. Code only: no ingestion run, no DB write. Prod stays `9bf0bc7a23bc95508968abe2025ceae3787a1bed`. `compute_similarity` and the 0.5 / 0.05 thresholds are unchanged. Implements the design in `~/carrec_kb_scratch/phase10i/CHECKPOINT.md` and owner decisions 2, 3, 5, 6, 7.

## 1. What changed
- **`ingestion/common/identity.py` (new):** trim identity (letter/digit runs, edition words anywhere in the name, seats, battery), plus attributes from structured field, then slug, then name. Hard filters on stated fuel, gearbox family, specific automatic type, displacement and drivetrain. Tie-breakers narrow only. Held editions: 815, 816, 821, 833.
- **`ingestion/common/resolver.py`:** returns a `Resolution` (still unpacks as `(variant_id, status, base)`) with `match_type`, `reasons`, `suggested_variant_id`. Only a unique identity match is `resolved`. Fuzzy and alias hits are hints for a reviewer, and an edition candidate no longer attaches a value.
- **`ingestion/common/updater.py`:**
  - provenance only for `resolved` + `identity_exact`;
  - aggregators only corroborate (P2): a value they would have written is recorded `pending`;
  - edition cells are never written (P8);
  - a variant is never created automatically (Finding C).
- **CarWale:** the served page's `versionName` must equal the requested one, else `page_mismatch`, stored with no write.
- **v3cars:** it no longer hard-codes `resolved`.
- **91wheels:** imports fixed (it failed at import), resolver unpacking fixed, `batch_runner` import fixed.
- **Runners:** the CarWale, v3cars and 91wheels runners require `--db`.
- **DB paths (decision 5):** `knowledge_base/kb_db.py` adds `KB_PATH` and `open_kb`, which refuses a missing file instead of creating one. `codemod_db_paths.py` moved every tracked script off a relative KB path: root scripts, `scratch/`, `knowledge_base/db/`, report helpers. Rewritten as text and syntax-checked; **none was run**. `migrate_v6.py` (creates the DB on purpose) and the historical `apply_phase*`/`verify_phase*` scripts (explicit path, must stay the exact scripts that ran) are unchanged. `cp`/`shutil` shell strings still use a relative path but fail loudly and don't open the DB.
- **Decision 6:** `ingestion/carrec_kb.db` is untracked, so it isn't in this PR (NEEDS_YOU N1).

## 2. Tests
`knowledge_base/tests` by explicit path: 417 passed, 5 failed.
- The 5 failures also fail on the unmodified branch and are unrelated to the resolver: 4 in `test_variant_column_matrix` need brochure PDFs that a worktree doesn't have, and `test_borderless_spatial` calls a method that no longer exists.
- New: `test_resolver_10i.py` (fixture of all 1,902 observations with 10H labels), `test_db_paths.py`.
- Owner regressions (decision 7): obs 1151 → 693, 1157 → 694, 955 → 191; Creta dual tone 16 / silent 15; obs 1248 goes to review and a stated-gearbox form returns `held_edition` 821; `ingest_91wheels` imports and runs.
- Updated on purpose, 4 existing tests: ambiguous match is `needs_review`; a verified alias isn't auto-accepted; `edition_candidate` doesn't create a variant; an aggregator doesn't write.
- Paper tests: 58 passed.

## 3. Replay of all 1,902 resolved observations (`replay.py`, `replay_summary.txt`; read-only on a copy)
| 10H class | auto, same | auto, other | review | edition | unresolved | page mismatch |
|---|---|---|---|---|---|---|
| OK (1,104) | 745 | 23 | 119 | 1 | 7 | 209 |
| MISLINK_TARGET (584) | 0 | 284 | 70 | 1 | 13 | 216 |
| MISLINK_NONE (152) | 0 | 5 | 31 | 25 | 46 | 45 |
| EDITION_NOT_IN_KB (56) | 0 | 7 | 4 | 41 | 4 | 0 |
| REVIEW (6) | 5 | 0 | 1 | 0 | 0 | 0 |

No mislink or edition observation keeps its old variant. The 5 REVIEW auto-accepts are the Fortuner rows a blind subagent judged correct; the sixth is 833. The rule partly follows the 10H classifier, so the independent test is P15's blind check of 50 auto-accepted links after merge.

## 6. Schema
None.

## 7. Branch
`kb/10i-resolver`, PR into `kb/policy-20261106`.

## 8. Prod SHA-1
Unchanged.

## 9. Message for the ranking track
KB resolver fix ready for review; no data changed.

## 10. Deferred
Re-ingestion and re-linking: item 9 (G3). The P15 check runs after the owner merges this PR.
