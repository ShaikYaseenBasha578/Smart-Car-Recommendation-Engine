# Update update_rehearsal_resume_2026-11-17

Started 2026-11-16T20:21:43Z. Mode: no-write (nothing written, pushed or opened), quick. KB SHA-1 at start: `efaa259c`.

## Stages

| # | Stage | Status | Result | Source |
|---|---|---|---|---|
| 1 | preflight | done | KB free, SHA-1 efaa259c, 31 GB free | `state.json` |
| 2 | specs | done | discovery DISCONTINUED_CANDIDATE 1, EXISTING 91, NEW_MODEL 16, NOT_ON_SALE 289, ONE_SITE_ONLY 14, OUT_OF_SCOPE 11, REVIEW_MODEL 1, UPCOMING 88; 7 model(s) processed, 1825 change(s) staged only | `runs/update_rehearsal_resume_2026-11-17_specs` |
| 3 | brochures | skipped | skipped by --quick | `state.json` |
| 4 | reviews | done | 0 model(s) read, 0 change(s) staged; no numbers re-check | `runs/update_rehearsal_resume_2026-11-17_reviews_2` |
| 5 | text | skipped | skipped by --quick | `state.json` |
| 6 | saved | skipped | skipped by --quick | `state.json` |
| 7 | audit | skipped | --no-verify: no verifier calls, so nothing to audit | `state.json` |
| 8 | export | done | exported into the workspace (2 file(s) differ from origin/main: data/catalogue_v3/catalogue.csv, data/catalogue_v3/catalogue_meta.json) | `runs/update_rehearsal_resume_2026-11-17/app` |
| 9 | checks | skipped | skipped by --skip-stages | `state.json` |
| 10 | pages | done | project pages regenerated and synced into the workspace (updated: index.html, pipeline.html, kb.html, engine.html) | `runs/update_rehearsal_resume_2026-11-17/app/pages` |
| 11 | pr | done | no-write: committed 6 file(s) to data/kb-update-2026-11-16 in the scratch workspace only (dba5853); nothing pushed, no pull request | `state.json` |
| 12 | summary | running | written | `runs/update_rehearsal_resume_2026-11-17` |

## What changed in the KB

- **specs** (source: `runs/update_rehearsal_resume_2026-11-17_specs/run.json`): models 92 -> 92, variants 1464 -> 1464, filled cells 38534 -> 38534. Change-set (source: `runs/update_rehearsal_resume_2026-11-17_specs/changeset.json`): cell:AGGREGATORS_CONFIRM 1825, price changes 69.
- **reviews** (source: `runs/update_rehearsal_resume_2026-11-17_reviews/run.json`): 0 change(s) staged.

## Verification

- Audit: --no-verify: no verifier calls, so nothing to audit

## App evaluation (before -> after)

- skipped by --skip-stages

## Withheld and why

- Cells left blank (source: `flags.tsv` of the specs and brochure runs): SINGLE_SOURCE 60, NO_SOURCE 28, POWERTRAIN_DIFFERS 18, VARIANT_NOT_ADDED 14.

## What needs you

- specs: 27 review item(s) in `runs/update_rehearsal_resume_2026-11-17_specs/REVIEW_update_rehearsal_resume_2026-11-17_specs.md` (source: `runs/update_rehearsal_resume_2026-11-17_specs/pending.json`). Tick them, then run `kbpipe apply-review <file>` and `./bin/kbpipe update --resume --redo export --label update_rehearsal_resume_2026-11-17`.

## Pull request

- no-write: committed 6 file(s) to data/kb-update-2026-11-16 in the scratch workspace only (dba5853); nothing pushed, no pull request

## Warnings

- none

## Stopped?

- Nothing stopped.
