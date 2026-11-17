# Update update_rehearsal_2026-11-17

Started 2026-11-16T19:37:31Z. Mode: no-write (nothing written, pushed or opened), quick. KB SHA-1 at start: `efaa259c`.

## Stages

| # | Stage | Status | Result | Source |
|---|---|---|---|---|
| 1 | preflight | done | KB free, SHA-1 efaa259c, 32 GB free | `state.json` |
| 2 | specs | done | discovery DISCONTINUED_CANDIDATE 1, EXISTING 91, NEW_MODEL 16, NOT_ON_SALE 289, ONE_SITE_ONLY 14, OUT_OF_SCOPE 11, REVIEW_MODEL 1, UPCOMING 88; 7 model(s) processed, 1825 change(s) staged only | `runs/update_rehearsal_2026-11-17_specs` |
| 3 | brochures | skipped | skipped by --quick | `state.json` |
| 4 | reviews | done | 0 model(s) read, 0 change(s) staged; no numbers re-check | `runs/update_rehearsal_2026-11-17_reviews` |
| 5 | text | skipped | skipped by --quick | `state.json` |
| 6 | saved | skipped | skipped by --quick | `state.json` |
| 7 | audit | skipped | --no-verify: no verifier calls, so nothing to audit | `state.json` |
| 8 | export | done | exported into the workspace (1 file(s) differ from origin/main: data/catalogue_v3/catalogue_meta.json) | `runs/update_rehearsal_2026-11-17/app` |
| 9 | checks | done | tests 914 passed in 622.84s (0:10:22); evaluation zero-violation queries 193 of 193 -> 193 of 193, verified 180 of 193 -> 180 of 193 | `runs/update_rehearsal_2026-11-17/app` |
| 10 | pages | done | project pages regenerated and synced into the workspace (updated: index.html, pipeline.html, kb.html, engine.html) | `runs/update_rehearsal_2026-11-17/app/pages` |
| 11 | pr | failed | refused: the app worktree /Users/shaikyaseenbasha/carrec_worktrees/recsys-v3 has uncommitted changes to tracked files (M data/image_manifest.csv;  M tests/test_images.py). Commit or stash them, then r | `state.json` |
| 12 | summary | pending | written | `runs/update_rehearsal_2026-11-17` |

## What changed in the KB

- **specs** (source: `runs/update_rehearsal_2026-11-17_specs/run.json`): models 92 -> 92, variants 1464 -> 1464, filled cells 38534 -> 38534. Change-set (source: `runs/update_rehearsal_2026-11-17_specs/changeset.json`): cell:AGGREGATORS_CONFIRM 1825, price changes 69.
- **reviews** (source: `runs/update_rehearsal_2026-11-17_reviews/run.json`): 0 change(s) staged.

## Verification

- Audit: --no-verify: no verifier calls, so nothing to audit

## App evaluation (before -> after)

- constraint satisfaction (queries with zero violations): 193 of 193 -> 193 of 193 (source: `runs/update_rehearsal_2026-11-17/app/eval_after.json`)
- verified satisfaction: 180 of 193 -> 180 of 193 (source: `runs/update_rehearsal_2026-11-17/app/eval_after.json`)
- shortlist recall@8: 0.755 -> 0.755 (source: `runs/update_rehearsal_2026-11-17/app/eval_after.json`)
- shortlist MRR: 0.7884 -> 0.7884 (source: `runs/update_rehearsal_2026-11-17/app/eval_after.json`)
- App tests: 914 passed in 622.84s (0:10:22) (source: `runs/update_rehearsal_2026-11-17/app/tests.log`)

## Withheld and why

- Cells left blank (source: `flags.tsv` of the specs and brochure runs): SINGLE_SOURCE 60, NO_SOURCE 28, POWERTRAIN_DIFFERS 18, VARIANT_NOT_ADDED 14.

## What needs you

- specs: 27 review item(s) in `runs/update_rehearsal_2026-11-17_specs/REVIEW_update_rehearsal_2026-11-17_specs.md` (source: `runs/update_rehearsal_2026-11-17_specs/pending.json`). Tick them, then run `kbpipe apply-review <file>` and `./bin/kbpipe update --resume --redo export --label update_rehearsal_2026-11-17`.

## Pull request

- refused: the app worktree /Users/shaikyaseenbasha/carrec_worktrees/recsys-v3 has uncommitted changes to tracked files (M data/image_manifest.csv;  M tests/test_images.py). Commit or stash them, then resume with --redo pr.

## Warnings

- none

## Stopped?

- Stage **pr** failed: refused: the app worktree /Users/shaikyaseenbasha/carrec_worktrees/recsys-v3 has uncommitted changes to tracked files (M data/image_manifest.csv;  M tests/test_images.py). Commit or stash them, then resume with --redo pr.
- Resume with exactly: `./bin/kbpipe update --resume --label update_rehearsal_2026-11-17`
