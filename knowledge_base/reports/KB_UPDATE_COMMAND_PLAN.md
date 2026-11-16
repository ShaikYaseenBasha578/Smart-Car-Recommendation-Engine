# Plan: one command to update the KB and the app

Status: **waiting for owner approval** (16 Nov 2026). Nothing is built.

## 1. What you get

```bash
./bin/kbpipe update
```

One command that brings the KB up to date with the market and prepares the app to show it. It ends with a pull request for you to merge and a review file for you to tick. It never deploys by itself and never applies a change to an existing value without your approval.

## 2. What it runs, in order

| # | Stage | Existing command it wraps | Uses an LLM |
|---|---|---|---|
| 1 | Preflight: KB free, hash recorded, backup, disk space, quotas | `kbpipe status` | No |
| 2 | Specs: new models and variants, changed prices and specs | `kbpipe run` | Verifier only |
| 3 | Brochures: for models added in stage 2 and models with many blanks | `kbpipe run` brochure layer | Sonnet reads, Opus checks |
| 4 | Reviews: expert scores and owner ratings | `kbpipe reviews --no-text` | No |
| 5 | Review text: expert notes and owner themes, only for new or changed pages | `kbpipe reviews` | Sonnet writes, Opus checks |
| 6 | Saved Team-BHP pages, if the folder has new files | `kbpipe reviews --import-saved` | Sonnet writes, Opus checks |
| 7 | Audit of what changed in this update | `kbpipe run --audit changed` | Verifier |
| 8 | Export catalogue and review files to the app | `scripts/export_*_from_kb.py` in the app repo | No |
| 9 | App checks: tests, evaluation, regenerate golden files only where the catalogue moved | app test suite, `eval/run_eval.py` | No |
| 10 | Project pages: regenerate and sync into the app | `kbpipe.dashboard`, `sync_project_pages.py` | No |
| 11 | Branch, commit, push, open a pull request with a summary | `git`, `gh` | No |
| 12 | Final report and review file | new | No |

Each stage already works on its own. The new work is the chaining, the stopping rules, the resume, and stages 9, 11 and 12.

## 3. Rules

- **Every stage keeps its own gates.** A failed gate stops the update at that stage. Earlier stages that passed stay written; nothing later runs.
- **Resume.** State is kept in `knowledge_base/runs/update_<date>/state.json`: each stage is pending, done, failed or skipped, with the KB hash before and after. `kbpipe update --resume` continues from the first stage not done. A stage that is done is never repeated unless `--redo <stage>` is given.
- **LLM limits.** When the subscription limit or a free quota is hit, the stage stops cleanly, the state says so, and the command prints when to resume. All LLM answers are cached, so a resume repeats no call.
- **Human steps stay human.**
  - Changes to existing values, removals and held models go to the review file. `kbpipe apply-review` applies your ticks, and `kbpipe update --resume` then refreshes stages 8 to 11.
  - The pull request is opened, never merged. Merging is the deploy and stays your click.
- **Nothing new in what may be fetched.** Same sites, same robots handling, same 4-second spacing. Team-BHP is never fetched; stage 6 reads only files you saved.
- **Never fabricates, never deletes rows, never touches `main` directly.**
- **Dry run.** `kbpipe update --no-write` runs every stage against a staging copy and shows what would change, with no KB write, no push and no pull request.

## 4. Flags

| Flag | Meaning |
|---|---|
| `--no-write` | Look only |
| `--resume` | Continue an interrupted update |
| `--only-stages specs,reviews` | Run a subset |
| `--skip-stages brochures,text` | Leave out the LLM-heavy stages for a quick price and variant refresh |
| `--max-models N` | Cap new models per update (default 40, as today) |
| `--no-pr` | Stop after stage 10; commit locally only |
| `--quick` | Same as skipping brochures, text and saved pages: no subscription allowance used |

## 5. What you see at the end

`UPDATE_SUMMARY.md` in the run folder, and printed to the terminal:

- models and variants added, prices changed, cells filled, by source;
- verification results for this update against the 95% and 98% bars;
- evaluation before and after on the app (constraint satisfaction, shortlist agreement);
- what was withheld and why;
- the review file path and how many items need you;
- the pull request link;
- anything that stopped, and the exact command to continue.

## 6. Build order

1. `kbpipe/update.py`: stage runner, state file, resume, `--no-write`. Stages 1–7 call the existing functions directly, not through the shell. Tests with fake stages for stop, resume and redo.
2. Audit resume (the missing piece from the earlier list), needed for stage 7.
3. Stage 8–10 adapter: the app repo path comes from config; it runs the exporters and the app's tests in the app's own virtualenv.
4. Stage 11: branch `data/kb-update-<date>` from the app's `main`, commit only data, golden files and project pages, push, open the pull request. Never force-push, never commit to `main`.
5. Summary writer and README section.
6. Full `--no-write` rehearsal, then one real `--quick` update, then one full update.

Sonnet builds; Opus or Fable reviews steps 1, 4 and 6. Estimate: one to two days of Sonnet work across usage windows.

## 7. Decisions for the owner

- **U1. Where the pipeline code lives.** Today `kb/kbpipe` is a local branch only. The command needs both repos on disk. Recommended: push `kb/kbpipe` to GitHub as its own branch (not merged into `main`), so the code is backed up and visible. Alternative: keep it local.
- **U2. Default depth.** Recommended: plain `kbpipe update` runs everything; `--quick` is the cheap weekly refresh. Alternative: make quick the default and require `--full` for brochures and text.
- **U3. Checker model.** Recommended: keep Opus as checker for text and brochure images, Gemini and Groq as fallbacks. This uses subscription allowance.
- **U4. Scheduling.** Recommended: manual for now, as decided before. A weekly scheduled `--quick` run could be added later.
- **U5. Golden test files.** Stage 9 regenerates them when only the catalogue moved. Recommended: allow this, and list each regenerated file in the pull request.

## 8. Risks

- **Two repos, one command.** A failure in the app's tests after the KB is already written leaves the KB ahead of the app. That is safe (the app reads its own exported files) and the summary says so.
- **Usage limits** will interrupt full updates. Resume makes that an inconvenience, not a failure.
- **Site layout changes** stop the affected stage with a clear message; nothing is written for that source.
- **Review data and brochures cost allowance.** `--quick` avoids both.
