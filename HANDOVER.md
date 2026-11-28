# CarRec handover (rewritten 17 Nov 2026, final Fable update)

For whoever continues this work (Opus or a new session). Read this file first, then the documents it names. Nothing here depends on chat history. The file name keeps its old date so existing references still work.

## 0. State in one minute

- **Live site:** carrec.onrender.com, deployed by Render from `main` of the app repository. Recommender v3 on the 1,556-variant, 101-model catalogue is the default (since pull request 41, merged 21 Nov). See the 21 Nov addendum.
- **KB:** 105 models, 1,619 variants (SHA-1 `0c8156b7…`; 101 models and 1,556 priced variants reach the app), three evidence layers (specs and brochures, expert reviews, owner ratings and themes). Production file `knowledge_base/carrec_kb.db` in the main checkout.
- **Pipeline:** `kbpipe` in `~/carrec_worktrees/kb-kbpipe`, branch `kb/kbpipe`, **pushed to GitHub on 17 Nov** as its own branch (not merged into `main`). One command, `./bin/kbpipe update`, runs 13 stages from discovery to a pull request.
- **First real update done (17 Nov):** `./bin/kbpipe update --quick` ran all 13 stages and opened pull request 35 (merged by the owner). It added no models. See section 3.
- **A copy of this file** is on GitHub in branch `kb/kbpipe` (`HANDOVER.md` at the root), as of 17 Nov.
- **The real to-do list** is section 6. The blind audit (`knowledge_base/reports/BLIND_AUDIT_2026-11-16.md`) is the honest outside view; read its top ten findings.

## 1. Rules the owner set

- **Plan first.** Every new feature gets a written plan and the owner's approval before any code. Bug fixes against an approved plan need no new plan.
- **Who does what.** The strongest model designs and reviews. Sonnet subagents write code and do bulk work. Free models (Gemini, Groq) where they work. Haiku is never a verifier (it gave false mismatches). A checker is never the same backend as the writer.
- **Reuse.** Use what is on disk before building or downloading anything.
- **UI.** Load the `impeccable` skill for all UI work, including in subagents.
- **Never** force-push, merge a pull request, commit to `main`, or delete files without the owner's approval. The owner clicks merge, and merging to `main` is the deploy.
- **KB policy** P1–P18 is in `CLAUDE.md` (repo root of the main checkout). The production KB is opened only through a controlled write: backup, script, dry run on a copy, idempotency re-run, apply, integrity check, compare.
- **P11 side files.** Any `-wal` or `-shm` file beside the production KB means stop and ask. See section 5, item 1.
- **Never write under** `knowledge_base/sources/oem/`.
- **API keys** come from environment variables, never from code. No paid services without approval.
- **Sources:** section 8.
- **Images:** only from the maker's own brochure PDFs on disk. Nothing is downloaded from the web.
- **GitHub branches** need tidying (about 30 local branches in the app repository). Lowest priority; never delete or merge without asking.
- The paper has a frozen KB snapshot and is not the focus.

## 2. Where things are

| What | Where |
|---|---|
| Main checkout | `~/Car_recommender_app/Flask Based App with Used Cars Function`, branch `paper/v0`. Holds the KB, backups, brochures, reports and this file |
| KB (production, not in git) | `knowledge_base/carrec_kb.db`. SHA-1 `7e5478c54f966c8dde64ef294d2463669da57483` after the 17 Nov update |
| KB backups | `knowledge_base/backups/`. Latest: `pre_update_update_2026-11-17_20261117T060213Z.db`, before it `pre_safety_relink_20261116T191844Z.db` |
| KB history | `~/carrec_kb_history` (local git, tags `kb-run-<date>`) |
| Pipeline code | `~/carrec_worktrees/kb-kbpipe`, branch `kb/kbpipe`, head `353fd9b`, pushed to `origin/kb/kbpipe`. Docs: `kbpipe/README.md`. Own virtualenv `.venv-kbpipe`, created by `bin/kbpipe` |
| Pipeline run folders | `~/carrec_worktrees/kb-kbpipe/knowledge_base/runs/<label>/` (`RUN_SUMMARY.md`, `changeset.json`, review file). Summaries and review files are committed; change-sets, logs and database copies are local only |
| App repository | `~/carrec_worktrees/recsys-v3`, GitHub `ShaikYaseenBasha578/Smart-Car-Recommendation-Engine`. The worktree sits on `feat/new-model-images` (merged); `origin/main` is the truth |
| Update scratch clone | `~/carrec_kb_cache/update_ws/<label>/app`. Stages 8–11 work here, never in the app worktree |
| Plans | `knowledge_base/reports/`: `KBPIPE_DESIGN_SPEC.md`, `RECOMMENDER_DESIGN_PLAN.md`, `REVIEW_LAYERS_PLAN.md` (§9a text notes and themes), `KB_UPDATE_COMMAND_PLAN.md` (approved, decisions U1–U5) |
| Surveys | `REVIEW_LAYERS_SITE_SURVEY.md`, `REVIEW_LAYERS_ALTERNATIVES_SURVEY.md` |
| Audit | `knowledge_base/reports/BLIND_AUDIT_2026-11-16.md` |
| Engine documents | in the app repository: `docs/V3_REVIEW_2026-11-14.md`, `docs/V3_SHORTLIST_GAP_2026-11-15.md`, `docs/API_AND_DEPLOY.md`, `docs/AUDIT_FIX_2026-11-16_CRASH_RATINGS.md` |
| Evaluation | app repository `eval/run_eval.py`, results in `eval/results/` (`final_*.json`, `audit_fix_*.json`) |
| Owner's shortlists | `eval/shortlist_sheet.csv` (40, partly stale). Refresh sheet for the owner to fill: `recsys_eval/shortlist_refresh_sheet.csv` in the main checkout (22 queries) |
| Project pages | `/project`, `/project/pipeline`, `/project/knowledge-base`, `/project/engine` in the app, served from `project_pages/`. Generated by `python -m kbpipe.dashboard`, copied in by `scripts/sync_project_pages.py --src <app_build>` |
| Memory notes | `~/.claude/projects/-Users-shaikyaseenbasha-Car-recommender-app-Flask-Based-App-with-Used-Cars-Function/memory/` |

## 3. The first real update (17 Nov, finished)

Command, from `~/carrec_worktrees/kb-kbpipe`: `./bin/kbpipe update --quick --label update_2026-11-17`. All 13 stages finished with exit code 0 in about 25 minutes. Report: `knowledge_base/runs/update_2026-11-17/UPDATE_SUMMARY.md`.

| Stage | Result |
|---|---|
| 1 preflight | Backup written |
| 2 specs | KB `efaa259c` → `7e5478c5`. 0 models, 0 variants, 0 cells written. 1,825 existing cells given confirming evidence. 27 review items |
| 3, 5, 6 | Skipped by `--quick` |
| 4 reviews | Nothing to refresh |
| 7 audit | 154 cells: 153 match, 0 mismatch, 1 unreachable. First audit run inside `update` |
| 8 export | Only `catalogue_meta.json` differs from `origin/main` |
| 9 checks | 916 tests pass, 1 skipped. Evaluation unchanged: 193 of 193, verified 180 of 193 |
| 10 pages | Regenerated and synced |
| 11 pull request | **First real run. Opened https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/35** (catalogue timestamp and the four project pages). Not merged |
| 12 images | No candidates: Thar Roxx's brochure has no usable picture; three models have no brochure |
| 13 summary | Written |

What it showed:

- **The 16 "new models" cannot be added by the current rules.** Discovery lists them every run (ZR-V, Creta Electric, Syros EV, Comet EV, Hector Tomahawk EV and PHEV, ZS EV, BE 6 Sporteq, XUV 3XO EV, XUV400, Invicto, X-Trail, Tigor EV, Camry, Fortuner Legender, Urban Cruiser Ebella). On 13 Nov each got "no variant could be added": no variant of theirs links on both sites (mostly EVs whose variant names differ between sites, for example "34.5 kWh" against "345 kWh"). The pipeline remembers them as handled and skips them silently while their listings are unchanged. An earlier message to the owner said this update would add them; that was wrong. Adding them needs a decision: looser name matching for battery sizes, or accepting one site plus a brochure. That is a design change and needs a plan.
- **The summary line is misleading.** Stage 2 prints "NEW_MODEL 16" and "1825 change(s) written", which reads as new data. They are 16 known-unaddable models and 1,825 confirmations. Worth rewording.
- **Review file:** `knowledge_base/runs/update_2026-11-17_specs/REVIEW_update_2026-11-17_specs.md`, 27 items: 7 facelift flags (Elevate, Thar, Baleno, Brezza, Slavia, Glanza, Hilux), price changes on Syros (15 variants) and Elevate (7), 4 new Elevate ZX Plus variants, 27 Scorpio-N variants no longer listed, Tigor as a discontinued candidate.
- Side files were left beside the KB after the write; fixed and removed the same day. See section 5, item 1.
- `CLAUDE.md` production SHA line is updated. `KB_CHANGELOG.md` in the pipeline worktree has the update's entry (uncommitted).

## 4. What exists

### KB and pipeline
- **Spec layer:** discovery and extraction from CarWale and CarDekho with no LLM, strict variant linking, reconciliation, gates (schema, provenance, rows, explained, reviews), safe write, review file for changes to existing values, independent verifier. Robots rules are checked on every fetch under the truthful identity `kbpipe/1.0 (personal research; contact via repository)`.
- **Brochure layer** (`kbpipe/brochure.py`): Sonnet reads, Opus checks the page image, then Gemini. 2,201 blank cells filled for 23 of the 30 new models; no existing value changed.
- **Review layers** (`kbpipe reviews`): Autocar India expert scores (622 rows, 78 models), 496 notes and 342 quotes; CarWale owner ratings (650 rows, 88 models); owner themes (271 rows, 67 models). Tables `professional_assessment`, `owner_rating`, `owner_theme`.
- **Crash ratings:** six Bharat NCAP tests linked on 17 Nov by `kbpipe/migrations/safety_relink_20261116.py` (143 variants gained ratings).
- **Update command** (`kbpipe/update.py`, `update_stages.py`, `appstages.py`): 13 stages, `state.json`, flags `--quick --no-write --resume --redo --only-stages --skip-stages --max-models --no-pr --no-verify --label`.
- **Image step** (`kbpipe/images.py`, stage 12): candidates from brochures on disk for models without a photo. It never pre-fills a choice, because its top pick matched a by-eye choice for 7 of 28 models. Apply with `python -m kbpipe.images --apply <picks.json>`, then commit in the app worktree and open a pull request.
- **Tests:** 140 pass (`.venv-kbpipe/bin/python -m pytest kbpipe/tests -q`).
- **All LLM answers are cached on disk**, so reruns repeat no call.

### Recommender and app
- **v3** (`services/recsys/`): weighted multi-criteria score; class weights spec 0.60, expert 0.25, owner 0.15; a blank is never a match and every unmet or unverified requirement is named on the card; unrated crash score sits between 3-star and 4-star; "cheapest" is a price ordering; best-scoring variant per model with "also available from". Old engine: `RANKER=current` and `CARREC_CATALOGUE_DIR=data`.
- **Front end:** v3 card renderer in `static/script.js` and `static/style.css`, used when the response has `engine == "v3"`.
- **API, Docker, CI:** `api_service/` (FastAPI), `Dockerfile`, `docker-compose.yml` (web 5001, API 8000), `.github/workflows/ci.yml`. Docker builds and passes health checks locally. **CI has never run:** GitHub says the account is locked for a billing issue.
- **Photos:** 88 of 92 models. Thar Roxx, Hector Plus, Bolero Neo Plus and Tekton use the placeholder.
- **Tests:** 916 pass, 1 skipped.

### Measured numbers (new catalogue, before the 17 Nov update)

| Measure | v3 | Old engine |
|---|---|---|
| Shortlist recall@8 | 0.755 | 0.715 |
| Shortlist MRR | 0.788 | 0.832 |
| Constraint satisfaction, main set | 193 of 193 | 193 of 193 |
| Constraint satisfaction, second set | 104 of 106 | 104 of 106 |
| Verified satisfaction, main set | 180 of 193 | 175 of 193 |
| Verified satisfaction, second set | 94 of 106 | not recorded here |

The shortlists are partly stale (none of the owner's picks is a new model), so the MRR gap says little until they are refreshed. The second query set is no longer unseen.

Evidence behind KB cells: brochure 14.9%, two or more sites 44.4%, one site 4.5%, June import only 32.6%, none 3.7%. 772 of 1,464 variants have only June price evidence.

## 5. Next steps, in order

1. **Side files: fixed 17 Nov (commit `4c20215` on `kb/kbpipe`), not yet seen through a real write.** This machine's SQLite keeps `-wal` and `-shm` after a clean close. `kb.remove_side_files` now runs after every backup, checkpoint and write; it removes only an empty `-wal`, only when nothing holds the database, and checks the hash before and after. `kb.preflight` refuses any side file, as P11 says. 140 kbpipe tests pass. The two files beside the KB were removed with the owner's approval; hash unchanged at `7e5478c5…`, integrity ok. After the next real write, confirm nothing is left beside the KB. A script outside the pipeline (the `sqlite3` shell, DB Browser) will still leave them.
2. **Pull request 35 is merged** (17 Nov). **Pull request 36 (`kb/kbpipe` → `main`) must be closed, not merged:** GitHub offered it after the branch was pushed. The branch comes from the KB side of the repository, conflicts with the app, and merging to `main` is the deploy. Closing it keeps the branch. The owner has been told; it was still open when this was written.
3. **Plan how to add the 16 unaddable models** (section 3). Needs the owner's approval before any code. Cheapest option to propose first: normalise battery-size spellings ("34.5 kWh" and "345 kWh") in variant matching, then measure how many of the 16 link.
4. **Reword the stage 2 summary line** so "NEW_MODEL 16" and "1825 changes written" cannot be read as new data.
5. **Engine page** still says the verified-satisfaction figure is "being added"; the generator does not read it. Fix, regenerate, sync.
6. **Apply the owner's review ticks** when they arrive, then `./bin/kbpipe update --resume --redo export --label update_2026-11-17`.
7. **Run a full (non-quick) update.** It uses subscription allowance for brochures and review text and will stop on the 5-hour limit; `--resume` continues.

Done on 17 Nov and no longer open: `kb/kbpipe` pushed (plan decision U1); `KB_CHANGELOG.md` and run summaries committed; `CLAUDE.md` production SHA line updated (that edit is uncommitted in the main checkout, like this file).

## 6. Open work

### Needs the owner
- Fill `recsys_eval/shortlist_refresh_sheet.csv` (22 queries). Top item for judging the engine.
- Clear the GitHub billing lock so CI can run. Checked 17 Nov: the billing page is clean (GitHub Free, $0, nothing due), yet every job fails with "your account is locked due to a billing issue". Adding address details without a card did not lift it (re-run at 07:41 UTC failed). Community reports say a valid card or PayPal on file, cancelling any pending Copilot trial, or a GitHub Support ticket (Billing category) clears it. CI on this public repository costs nothing once unlocked.
- Tick the KB review file. Before this update: 1,174 differing cells including 500 prices, 187 unlisted variants, 36 duplicate groups. The newest file is `update_2026-11-17_specs/REVIEW_update_2026-11-17_specs.md`. Then `kbpipe apply-review <file>` and `./bin/kbpipe update --resume --redo export`.
- Decide the Punch and Tekton crash links (test 32 lists CNG variants only; test 21's variant list says Duster).
- Decide whether third-party notes and quotes stay on the public site.
- Read the tables `EXPERT_ASPECT_CRITERIA` and `OWNER_THEME_CRITERIA` in `services/recsys/config.py`; they were the builder's judgement, and most themes map to value for budget.
- Read Team-BHP's terms before saving any pages.
- Decide on a key for the LLM query parser (off by default, unproven).
- Approve the branch tidy-up.

### KB and pipeline
- 16 listed models cannot be added under the two-site rule (section 3). Needs a plan.
- Brochures downloaded but unread: Sierra, Sierra EV, Tayron. No usable brochure: Sorento, Hector Plus, Bolero Neo Plus, Tekton.
- No Autocar review for Sorento, Tigor, Venue N Line, i20 N Line, Creta N Line, Hector Plus; Thar's page lacks one aspect.
- Team-BHP import (`--import-saved`, `--teambhp-links`) is tested only on a synthetic file.
- A model-year dimension would resolve the held models (Seltos, Brezza, Baleno, WagonR, Jimny, Kylaq). It needs a schema change and has never been planned.
- Open defects listed in `CLAUDE.md` (editions 833, 821, 815, 816; unverified CNG figures; resolver fix before the ingestion freeze lifts).

### Recommender
- A fresh, unseen query set.
- Four sedan probe cases: a car known to lack a feature ranks above a sedan whose comfort cells are blank. Known limit of the stress test; lowering the coverage penalty does not fix it.
- Live latency not re-measured after the speed fix (0.64 s → 0.27 s locally).
- The owner bar sits at 95–97 for most cars and separates them poorly. Dark mode and 360px width were not checked by hand.
- Tool-calling advisor (plan §10) is not built.

## 7. Lessons

- Delegate building to Sonnet from the start; keep design and review with the strongest model.
- Survey a source's terms and page structure before choosing it.
- Run the evaluation on a prototype before building a scoring change. The cheapest-variant rule cost a day.
- Run the planned re-check before a write, not after.
- State results as measured, not expected. Two claims had to be corrected after the blind audit ("cheapest car" fixed; constraint satisfaction 100%), and "the update will add 16 new models" was a third.
- Push before the owner merges. Pull request 32 was merged a minute before a late commit, which needed pull request 33.
- Export to the app alongside every KB change, or the app silently lags.

## 8. Source decisions (owner)

- **Autocar India:** accepted as a non-commercial, terms-grey source. Robots obeyed, one page per model, off switch `reviews.sources.autocar.enabled`.
- **CarWale** user ratings and written reviews: accepted.
- **Team-BHP:** never fetched by any tool. The owner may save pages by hand (the SingleFile browser extension was suggested); the tool reads local files only. A request to build an auto-saver was declined.
- **CarDekho expert scores, YouTube, Reddit:** not used. No permission emails.
- A source that blocks a fetch is never worked around.

## 9. Quotas

- Gemini free: about 500 calls a day (`gemini-3.5-flash-lite`; `gemini-3.8-flash` hangs or returns 503). Groq free: refuses after about 250 calls or on token limits.
- The Claude subscription's 5-hour limit stops Sonnet agents often. Resume the same agent with a message after the reset; do not start a new one.

## Addendum, 17 Nov: a full update was started

- Started at the owner's request, from `~/carrec_worktrees/kb-kbpipe`: `./bin/kbpipe update --label update_full_2026-11-17` (brochures and review text included). Log: `knowledge_base/runs/update_full_2026-11-17.log`. State: `knowledge_base/runs/update_full_2026-11-17/state.json`.
- It was expected to stop on the subscription limit. Check `state.json`; continue with `./bin/kbpipe update --resume --label update_full_2026-11-17`. Finished stages are not repeated and cached LLM answers are reused.
- It may have written to the KB. Afterwards: record the new production SHA-1 here and in `CLAUDE.md`, confirm no `-wal` or `-shm` file sits beside the KB (first real test of the side-file fix), and check whether stage 11 opened a pull request.

## Addendum, 17 Nov evening: the full update finished (Opus)

- `update_full_2026-11-17` ran all 13 stages after two resumes. **KB SHA-1 `37b583ab3323fcac1e02ca7993a4d21a16a178af`** (also in `CLAUDE.md`). No side files beside the KB.
- Brochure stage: 21 models read across two writes. Net: 217 blank cells filled on 34 Sierra variants, 153 observations and 2,707 evidence rows added, no existing value changed. The 16 models missing from the KB gained no variants (matching rule unchanged). The final redo wrote nothing (hash unchanged), which confirms idempotency.
- **Defect found and fixed** (`220b869`, pushed): the side-file clean-up made the post-write `mode=ro` integrity read fail after each write had committed. Now an immutable read; regression test added; 141 tests pass. The skipped post-write steps were done by hand and logged in `KB_CHANGELOG.md`.
- Review stages: nothing new to read. Audit: 157 of 157 cells match. App: 916 tests pass; evaluation unchanged (193 of 193, verified 180 of 193); golden file regenerated.
- **Pull request 37 merged by the owner (17 Nov, 14:45 UTC)**; no pull requests remain open (36 was closed): Sierra catalogue rows, timestamps, project pages and the regenerated golden file.

## Addendum, 18 Nov (Opus)

- **Pull request 38 open:** the engine page now shows the verified-satisfaction figures (180 of 193 main, 94 of 106 second set, old engine 175 of 193). The generator required every summary field to be a number and the file also has a text `scope` field. Fixed in `kbpipe/dashboard.py` with a test.
- **Stage messages reworded** (`7245e0a`): stage lines and `UPDATE_SUMMARY.md` now say blanks filled, values changed and confirmations, and "KB unchanged" when the hash did not move. "NEW_MODEL 16" now reads "16 model(s) found on both sites but not in the KB (0 added)". 143 kbpipe tests pass.
- **Plan for the 16 missing models:** `knowledge_base/reports/PLAN_ADD_MISSING_MODELS.md`, waiting for the owner. Measured cause: both sites list the variants, but none link. Blocks: battery size only in one site's name (8 models), "345 kWh" page spelling (XUV400), strong hybrids labelled "Petrol" by CarDekho (4), descriptor words (5), EV prices differing beyond 0.5%, and some genuinely different names. The earlier claim that the cause was mostly "34.5 vs 345 kWh" was wrong; that affects only XUV400.
- **Policy conflict to settle:** `CLAUDE.md` on `kb/kbpipe` has an owner decision of 2026-11-12 allowing an empty `-wal` and a `-shm` beside the KB when no holder, and saying never delete them. On 17 Nov the side files were deleted twice with the owner's approval in chat, and the pipeline now removes them after its own writes (`kb.remove_side_files`) and its preflight refuses any. The owner must choose which rule stands; then align the code or the policy text.
- **Commits to `paper/v0`:** none. P17 allows only a fast-forward of a `kb/*` branch, so the handover, plan and hash line are on `kb/kbpipe` (`HANDOVER.md`, `knowledge_base/reports/PLAN_ADD_MISSING_MODELS.md`, `CLAUDE.md`). The main checkout's copies are edited on disk but uncommitted.
- **91wheels as a third source (investigated 18 Nov):** technically easy (the old parser still works; battery size, hybrid labels and a price majority would unblock most of the 16 models) but its terms forbid scraping without permission. Not added; recorded as a future source conditional on written permission. Details and the build outline: `knowledge_base/reports/PLAN_ADD_MISSING_MODELS.md` §3b. The 16-model plan gained §3a: brochures settle spec disagreements already, cannot settle prices, and can confirm trim identity for linking.
- **Other sources (checked 18 Nov), and an inconsistency to settle.** The earlier survey (`knowledge_base/reports/REVIEW_LAYERS_ALTERNATIVES_SURVEY.md`) recorded that **CarDekho's terms explicitly ban scraping, derivative and commercial use**. That is why its expert scores were dropped, yet the spec pipeline reads CarDekho for every update and its two-site rule depends on it. The owner must decide whether CarDekho stays a spec source, on the same reasoning that rules out 91wheels. Other findings: Maruti's own website forbids extracting content without written consent; V3Cars needs written consent; ZigWheels is silent on bots but bars derivative use; terms for Hyundai, Tata, CarTrade, carandbike and the Autocar specs pages were not found at the usual addresses. Usable without any terms question: maker brochures and official price lists that the owner saves locally (read by the existing brochure layer), Bharat NCAP, government EV-scheme model lists (not yet checked), and Wikidata at model level (not yet checked). Paid option: JATO.
- **Owner decision, 18 Nov: keep CarDekho as a spec source for now**, knowing its terms ban scraping. The pipeline stays unchanged. Revisit if the project becomes commercial or CarDekho objects, and do not extend CarDekho use (for example to its expert or user reviews) without asking.

## Addendum, 18 Nov night: 16-model plan, steps 1-6 (Opus orchestrating, Sonnet building)

- **Steps 1-4 (Sonnet agent, commits e4f488e to 54c0462 on `kb/kbpipe`):** diagnostic, tiered linking rules (tier 0 = original linker unchanged), regression (1,295 of 1,295 old links identical), no-write run. Reports: `knowledge_base/reports/kbpipe/MISSING_MODELS_*.md`.
- **Step 5 (blind check, fresh Opus agent):** 57 of 57 sampled links agreed (100% in every rule class), 6 of 6 planted wrong pairs rejected. Records: `knowledge_base/reports/kbpipe/linkcheck_missing16/`.
- **Step 6 (write), `update_missing16_2026-11-18`, stopped at stage 7 (audit) on the free Gemini quota after 27 of 337 cells.** Stages 1-4 wrote: **KB 37b583ab -> 0c8156b72b813275a85c95b3fdde36db43295ab0**, 92 -> 105 models, 1,464 -> 1,619 variants (13 new models plus new variants on existing models), 2,605 + 635 blank cells filled, 0 stored values changed, 72 expert and 99 owner rating rows. Integrity ok, foreign keys 297, no side files. The process was then stopped from the app; nothing was mid-write.
- **Next:** when the Gemini quota resets, run `./bin/kbpipe update --resume --label update_missing16_2026-11-18` (audit, export, app checks, pages, pull request). Review file: `runs/update_missing16_2026-11-18_specs/REVIEW_*.md` (78 PRICE_DISAGREES, 56 NEW_VARIANT, 44 PRICE_CHANGE, 134 VALUE_CHANGE, and others). Held: ZR-V, X-Trail, Hector Tomahawk PHEV (names genuinely differ).

## Addendum, 21 Nov: the 16-model update finished (Opus orchestrating, Sonnet building)

- **`update_missing16_2026-11-18` ran to the end.** Audit: 337 cells, 333 match, 0 mismatch, 2 unreachable. No KB write after 18 Nov; prod SHA-1 is still `0c8156b72b813275a85c95b3fdde36db43295ab0`.
- **App pull requests, all merged by the owner:** 39 (README rewrite), 40 (tests and exporter made catalogue-independent: golden file per catalogue size, size and model counts read from the catalogue, unpriced variants left out of the export, EV range may be missing, Innova Hycross/Invicto added as the fifth twin pair), 41 (the data update itself: 1,556 variants of 101 models, 63 unpriced variants excluded and listed in `catalogue_meta.json`, `tests/data/golden_empty_evidence_1556.json`).
- **Evaluation on the new catalogue:** main 193 of 193 answered with zero violations, 181 verified; held-out 107 answered, 105 zero violations (the same two known cases), 91 verified; recall@8 0.745, MRR 0.789 (40 shortlists).
- **Open README pull request 42** refreshes the README figures (owner to merge).
- **kbpipe fixes on `kb/kbpipe`:** f899ece (golden regeneration for any catalogue size), 3a6ea9d (`ensure_workspace` fetches origin, so a redo export never builds on a stale `main`), 54826ab (summary stage parsed the 17 MB change-set once per evidence item and ran for hours; now once per stage). 182 kbpipe tests pass.
- **Lesson:** a resumed run must not overlap an older run of the same label. Two processes were alive at once on 21 Nov; the stale one was stopped before it could overwrite `state.json`. Check `pgrep -fl "kbpipe update"` before resuming.
- **Still needs the owner:** tick the review files (392 specs items, 40 brochure items), mainly prices, so the 63 unpriced variants (including Comet EV, Hector Tomahawk EV, ZS EV and BE 6 Sporteq, which are absent entirely) can reach the app; pick photos for the 5 models with brochure candidates (13 models show a silhouette); 46 new EVs have no range.
- **Branch cleanup (22 Nov, owner-approved):** 28 clean worktrees removed and 47 branches deleted (local and GitHub), each checked to be fully contained in `main` or `kb/kbpipe` first. Kept: `main`, `paper/v0` (local only, 52 commits not on GitHub), `kb/kbpipe`, `kb/10i-resolver` and `kb/policy-20261106` (the Phase 10I resolver fix, not in `kb/kbpipe`), `kb/enrich-claude` (one unique commit), `deploy/new-car-v1` (rollback), `feat/new-model-images` (checked out in `recsys-v3`, which holds the app `.venv`). Worktrees left: main checkout, `carrec-deploy`, `kb-10i`, `kb-enrich-claude`, `kb-kbpipe`, `recsys-v3`. Worktrees named elsewhere in this file (`app-*`, `kb-10e`…`kb-10h`, `kb-main`, `kb-enrich-flash`, `carrec-*` except `carrec-deploy`) no longer exist; recreate with `git worktree add` if needed.

## Addendum, 22 Nov: EV range fill, Plans A and C (Opus orchestrating, Sonnet building)

- **EV range fill:**
  - KB `0c8156b7…` → `b15b7dcb…`; details are in the `KB_CHANGELOG.md` summary of 22 Nov.
  - Data pull request 45 (14 app ranges, plus Clavis EV dimensions and safety cells from its brochure). App EVs without a range: 40 → 26.
  - The brochure-run audits stopped on the free verifier quota; resume them with `--resume-audit`.
- **Owner rules of 22 Nov:**
  - CarWale "Expected Range" counts as the claimed range.
  - For EV range only, two sites within 10 km take the higher value.
  - Both are in memory and in kbpipe (`reconcile.decide`, `config.near_take_higher_km`).
- **Plan `reports/plans/PLAN_LLM_ML_RAG_2026-11-22.md`:** A and C approved, B on hold.
  - Pull request 43 (A: LLM parser pacing, 429 cool-down, resumable eval, 40 draft hard queries for the owner to tick).
  - Pull request 44 (C: cited explanations behind `RAG_EXPLAIN`, stacked on 43, with UI and screenshots).
  - Not done: A step 4 (paced on/off measurement, after the owner ticks the hard-query labels), and C's live evaluation and blind groundedness review. Both need the free LLM quota.
- **Rule-parser bug found (not fixed, owner to decide):** a word before "not" is negated too. "Tata SUV not diesel under 15 lakh" excludes Tata and SUVs; "Hyundai sedan not petrol" excludes Hyundai and sedans. No eval query uses this phrasing.
- **Worktrees added:** `kb-near-rule` (merged, can go), `app-llm-parser`, `app-rag`.

## Addendum, 22 Nov evening: merges, RAG evaluation, UI/UX plan

- **Merged by the owner:**
  - #43, #45 and #46. The negation bug in the line above is fixed by #46.
  - #44 landed in `feat/llm-parser-pacing` (it was stacked), so #47 carried it to `main`; also merged.
  - **Lesson:** don't stack PRs; branch each from the latest `main`.
- **RAG live evaluation (Gemini 3.5 Flash Lite, free tier):**
  - 113 live answers plus 9 cached, then the quota ran out; 198 queries fell back to the template text.
  - The checker passed about 97% of the cars the model actually wrote about.
  - Latency p50 3.1 s, p95 6.2 s, max 11.1 s. The 2 s default timeout would miss 107 of 113 calls; the new timeout is the owner's decision.
  - The rest of the run resumes from `eval/results/rag_cache.json` in `app-rag`, untracked. The prompt is now `rag2`, so old answers no longer match.
- **Blind groundedness check of 50 sentences:** 46 supported, 4 unsupported, 0 wrong.
  - The checker was tightened in **PR #48** (open): sentences citing only the query are rejected, and fit claims are allowed only when every requirement is met.
- **Groq vs Gemini:** the owner asked about the trade-off.
  - Groq is much faster, but its free-tier token limits are tight for our ~4,500-token calls.
  - A 50-query Groq trial was offered, not run.
- **UI/UX:**
  - Blind review of the live site: `knowledge_base/reports/plans/UIUX_REVIEW_2026-11-22.md`, 22 changes.
  - Plan: `PLAN_UIUX_2026-11-22.md`, approved with the default decisions. It is six PRs (A to F), built one at a time from the latest `main`.
  - **PR #49 (A, 12 quick wins)** is open. Next is PR B (the result card), after #49 merges.
- **Worktrees:**
  - added `app-uiux` (PR A);
  - can go once their PRs merge: `app-llm-parser`, `app-negation` and `kb-near-rule` now; `app-rag` after #48.
- **Still waiting on the owner:**
  - the hard-query labels (`eval/HARD_QUERIES_REVIEW.md`, all 40 unticked), which block Plan A step 4;
  - the review items (prices, the Windsor EV items);
  - the RAG timeout choice.
- **Later, 22 Nov:**
  - #48 and #49 were merged.
  - **PR #50 (UI plan B, the result card)** is open.
    - Desktop card medians are 330–373 px; they were 639–742.
    - Mobile medians are 719–797 px; they were 1,353–1,495. That is still 0–80 px over the 720 target. Going lower needs the owner's say on hiding "Also available from", the chips or a why bullet.
  - Next is PR C (details panel and car page), after #50 merges.
  - #50 was merged. **PR #51 (UI plan C, details panel and car page)** is open.
    - The inline panel went from 6,013 px to 833 px.
    - The variant table shows 8 matching rows and scrolls in its own box with a sticky header.
    - Variant pick: instant feedback, focus kept, `variant_id` in the URL.
    - The car page shows reviews when opened from a search; there is a gap when the model isn't in that search's results.
    - Next is PR D (unused words, uncovered brands, relaxation choices), after #51 merges.
- **23 Nov:** #51 merged. **PR #52 (UI plan D, what the search didn't use)** is open.
  - "Didn't use: X" chips come from an allow-list of car attributes (`services/recsys/ignored.py`). A stop-list was dropped because it would have put chips on 113 of the 369 eval queries.
  - The blind checks ran in three rounds. Shown chips were correct 80/80. Queries with no chip were right only 84–87% of the time, below the 95% bar. **The owner chose to ship the chips as built.**
  - Uncovered brands (Ferrari and 9 others) now show "We don't cover X".
  - The relaxation notice now has "Without <req> · n models" buttons (`relaxation.alternatives`).
  - The echo shows DCT, "No CVT" and "No AMT".
  - The eval is byte-identical and 1086 tests pass.
  - Vague queries are slow because every variant is scored (0.7 s locally, about 10 s on Render). The fix is in scoring, and the owner decides on it.
  - **Parser follow-up (its own PR, it changes parses):**
    - "nothing above 13 lakh" is read as above;
    - "under 4 metres" is read as a ₹4 lakh budget;
    - "tow a trailer" is read as the Triber;
    - "sunroof bilkul nahi" is read as Sunroof;
    - "can't drive a manual" is read as Manual;
    - "450 km range" and "high ground clearance" are not parsed;
    - "fast charging" is read as performance;
    - "nexon or punch" keeps only the Nexon;
    - "AMT nahi" adds Automatic.
  - Next is PR E (compare and sort), after #52 merges.
- **23 Nov:** #52 merged. **PR #53 (UI plan E, compare and sort)** is open.
  - Each result card has a Compare toggle (up to 4 cars, kept in sessionStorage). A tray is fixed to the bottom of the results page.
  - The new `/compare?ids=…` page is server-rendered (`services/compare.py`, `templates/compare.html`):
    - 12 rows. Spec cells go through the car page's `spec_item`, so unverified cells read "Not verified".
    - "Best" is marked per row. Mileage is ranked only within the same unit, and thin owner samples never win.
    - The first column is sticky on mobile.
  - Sort offers Best match, Price, Mileage and Safety, kept in `&sort=`. "Top pick" shows only in Best match order.
  - Desktop cards grew by 24 px (tallest 396 px, against the 380 px target), because the chips now sit on their own line above the three buttons.
  - The eval is byte-identical, 1115 tests pass, and the new compare gate passes 36/36.
  - **Stale:** the existing `tests/ui_gates.py` fails on main the same way. Its 340 px limit and the old panel headings predate PRs A–C, and it crashes at the detail-panel step. Updating it is a small follow-up.
  - Next is PR F (/project header and theme), after #53 merges. Then the final blind re-review.
- **23 Nov:** #53 merged. **PR #54 (UI plan F, /project header, intro and theme)** is open.
  - The /project pages get the site header at serve time (`templates/_project_header.html`, main links from the `_nav.html` macro). The generated pages themselves are not hand-edited.
  - One "Theme: Auto/Light/Dark" control works across the site (key `carrec-theme`). A head script applies the saved choice before first paint, and the `style.css` dark blocks honour `data-theme`.
  - Generator change (`kbpipe/dashboard.py`, 43fe321): the overview opens with a plain intro, and every page now uses one count wording.
    - The plan's "1,556 on sale" was wrong: the 63 variants the app leaves out have **no price**. Pages now say "1,619 stored; the app shows the 1,556 that have a price".
    - Pages were regenerated from a read-only copy (b15b7dcb). The only other differences are the date, the engine commit count (9 → 13) and the price age (147 → 148 days).
  - The owner reported a scrollbar in the search box. Fixed: the follow-up box was sized while its form was hidden (height 0), and search boxes no longer draw a scrollbar.
  - The eval is byte-identical, and 1130 tests pass.
  - **Open:** the engine page (367 px) and KB page (332 px at 320) are wider than small phones, from their generated content, same as on main. It's a generator follow-up.
  - All six UI plan PRs are done once #54 merges. Next is the final blind re-review of the live site (same brief, fresh Opus), after Render deploys.
- **23 Nov:** #54 merged and deployed. **Final blind re-review done** (fresh Opus, same brief, live site). The report is `knowledge_base/reports/plans/UIUX_REVIEW_2026-11-23.md`.
  - Scores, 22 Nov → 23 Nov:
    - first impression 8 → 8;
    - clarity 7 → 8;
    - result card 5 → 6;
    - detail page 5 → 6;
    - mobile 6 → **5**;
    - accessibility 7 → 7;
    - polish 7 → 7.
  - Two bugs are confirmed in code:
    - the title link has no `variant_id`;
    - the search text is set after the box is fitted, so it is clipped on load and on Back.
  - Mobile density is the main open area: results start about 740 px down, a card is about a screen tall, and compare shows 1.3 columns.
  - Any follow-up PR waits for the owner.
- **23 Nov:** follow-up plan written: `knowledge_base/reports/plans/PLAN_UIUX_FOLLOWUP_2026-11-23.md`. It is **awaiting owner approval**.
  - **PR G**, bugs and correctness:
    - the search box clipped on load;
    - the car link variant;
    - reasons hidden behind the reviews toggle;
    - "Not met: suv";
    - one "Not verified" wording;
    - the Compare button's name;
    - a skip link.
  - **PR H**, mobile density: target a median mobile card of at most 560 px, and the first card visible after a search.
  - Five owner decisions, with defaults.
- **23 Nov:** the follow-up plan was approved with its defaults. **PR #55 (follow-up G, bugs and correctness)** is open.
  - **Search box:** it is re-sized after the code sets the text, so it is no longer clipped on load or Back (mobile 72/48 → 72/72).
  - **Car link:** it carries `variant_id`. The Sonet case was checked: the HTK Plus Diesel AT card now opens on that variant, not the HTE Petrol MT.
  - **Reasons:** they have their own "+N more reasons" toggle, and the budget reason is always shown (found by `fields == ["price_ex_showroom"]`).
  - **Wording:** "Not met: SUV, not a sedan" (mapped in the browser; `relax.py` untouched), and "Not verified" everywhere.
  - **Mileage:** 1 decimal on the car page and compare.
  - **Accessibility:** the Compare button's `aria-label` is read once, and there are skip links.
  - The eval is byte-identical, 1169 tests pass, and the compare gate passes 36/36.
  - Next is PR H (mobile density), after #55 merges.
- **23 Nov:** #55 merged. **PR #56 (follow-up H, mobile density)** is open.
  - Measured at 375 px, main → this PR:
    - median card 772 → 621 (target 560, **missed**);
    - first card's top after a search 777 → 360 (target 300, **missed**);
    - compare: 1 → 2 full columns;
    - the variants table no longer scrolls inside the page.
  - Desktop median 396 → 353.
  - Going further needs an owner call: text under 13 px, buttons under 44 px, or dropping a piece of the results header (about 290 px above the first card).
  - The phone compare header is not sticky; a sticky header would need an inner scroll trap.
  - "Show differences only" (`/compare?diff=1`) is server-side.
  - The eval is byte-identical, 1188 tests pass, and the compare gate passes 36/36.
  - After #56: PR I (Back cache) and PR J (car page) are only planned if the owner asks.
- **23 Nov:** the owner chose to merge #56 as is. No further phone-density pass for now. PR I (Back cache) and PR J (car page) stay unplanned until asked.
- **23 Nov:** #56 merged. The follow-up plan (PR G and PR H) is complete.
- **23 Nov:** the owner asked for the five open follow-ups in one go. The plan is `knowledge_base/reports/plans/PLAN_FIVE_FOLLOWUPS_2026-11-23.md` (six PRs: gates, /project overflow, faster vague searches, parser fixes, Back cache, car page), **awaiting approval**.
- **23 Nov:** the five-follow-ups plan was approved. The owner changed two decisions: "under 4 metres" becomes a real hard length filter, and "high ground clearance" becomes a ranking preference (both in PR 4). PRs 1–3 started in parallel.
- **23 Nov:** PRs 1–3 of the five-follow-ups plan are open. They touch no common file, so they can be merged in any order.
  - **#58, the UI gates (606/606):**
    - It runs desktop, laptop and mobile, each light and dark. The browser path is set by `CARREC_CHROMIUM` and the wait by `CARREC_GATE_TIMEOUT_MS`.
    - The fix the gates found: the phone EV facts line hides "(single-speed EV)", taking the EV median from 646 to 621 px.
  - **#57, the /project overflow:**
    - It is CSS in the generator (kb/kbpipe d5c2228), regenerated from the read-only copy b15b7dcb; there are no text changes.
    - Engine went 367 → 320 px and KB 332 → 320 px.
  - **#59, vague-search speed:**
    - "good car" went from 0.67 to 0.17 s locally.
    - Full responses for 329 queries are byte-identical, with exact floats, on Python 3.12 (production pins) as well as 3.9.
    - `tests/test_criteria_cache.py` was added. Per-row criteria *detail* may list empty extra fuel fields; no response uses it.
  - Next is PR 4 (the parser, with the length filter and the clearance preference), from main after these merge. Then PR I and PR J.
- **23 Nov, later:** the owner merged #57, #58 and #59.
  - **Render timing:** "good car" now takes 2.57 s warm (median of 5), down from 9.6 s. "SUV under 15 lakh" takes about 1.6 s.
  - **#60, PR 4 (parser):** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/60, branch `fix/parser-misreadings`, worktree `~/carrec_worktrees/app-parser`. It contains:
    - the misreading fixes;
    - `max_length_mm` (shown as "Under 4 m long");
    - the `ground_clearance` rule-only soft preference (conditional criterion, weight 0 and hidden unless asked);
    - the typo guard (`typos.ENGLISH_WORDS`).
  - **#60 results:**
    - 22/391 parses changed, all intended, 6 of them eval queries, so no blind review was needed;
    - main eval identical; held-out only h-060 changed (precision up);
    - pytest 1289 passed; gates 606/606.
  - **#60 not done:** the other `max_*` bounds have no echo chip; "CVT nahi" still sets the automatic family; with the LLM parser on, `llm_parse.py:731` would drop the rule-only preference.
  - **Next:** PR I (Back cache) from main after #60 merges, then PR J.
- **23 Nov, later:** the owner merged #60 and asked for PR I and PR J together. Both were built in parallel, each from main 1b556ba (Sonnet builders, Opus review and reruns).
  - **#61, PR I (Back cache):** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/61, branch `feat/back-cache`, worktree `~/carrec_worktrees/app-backcache`.
    - `/predict` answers are kept in `sessionStorage` (`carrec.results`) for 30 minutes, at most 12, keyed by `[data_as_of stamp, query, drops]`. The stamp reaches the page as `data-catalogue` on `<main>`.
    - Back, forward and "Back to search" draw the saved answers with no `/predict` call. The whole thread, scroll position, open panels, reasons, reviews, sorts and chips are restored from `history.state`.
    - A reload or a typed address still fetches.
    - Results: gates 650/650 (new `backcache_checks`); pytest 1289 passed.
  - **#62, PR J (car page):** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/62, branch `feat/car-page`, worktree `~/carrec_worktrees/app-carpage`.
    - All matching variants are shown, with a "Tinted rows match your search" legend.
    - `/api/car` gives reviews with no query, via `car_detail._model_reviews` (the cards' explain functions with no query weights). With a query nothing changes: 20 pairs are identical to main.
    - A sticky "On this page" menu, and "Add to compare" on the car page.
    - A header tightening at widths under 360 px (it overflowed by 37 px at 320 on every page).
    - Results: gates 750/750 (new `carpage_checks`); pytest 1291 passed; eval unchanged.
  - **Combined:** the two branches merge without conflicts, and the combined tree passes pytest (1291) and gates (794/794). Whichever merges second gets main merged into its branch (no force-push).
  - **Next:** nothing planned. Small follow-ups from #60 and the owner items stay on the agenda.
- **23 Nov, end:** the owner merged #61 and #62. Main (71d5a65) has the same tree as the combined tree tested before the merge (794/794 gates).
  - Live on Render: `/car/kia/sonet` has reviews with no query. On a phone, Back from a car page made 0 `/predict` calls and returned to the same scroll position.
  - **Nothing in progress.**
- **26 Nov:** the owner approved the plan for the three #60 follow-ups (`knowledge_base/reports/plans/PLAN_PR60_FOLLOWUPS_2026-11-26.md`).
  - **#63, PR K:** https://github.com/ShaikYaseenBasha578/Smart-Car-Recommendation-Engine/pull/63, branch `fix/pr60-followups`, worktree `~/carrec_worktrees/app-followups`.
    - Chips and units for the other five upper limits (`MAX_LABELS`, `MAX_UNITS`).
    - A negated gearbox type only excludes that type, with no family (`_parse_transmission`).
    - The `llm_parse.merge` rebuild keeps `RULE_SOFT_PREFERENCES`. The prompt's SHA-256 is pinned in a test.
  - **Results:**
    - only hq-020 changed of 391 parses;
    - main and held-out eval identical;
    - hard counts unchanged (transmission-family agreement 86.7% → 92.9%);
    - pytest 1300 passed; gates 794/794.
  - **Next:** nothing planned. Owner items and the KB backlog remain.
- **28 Nov, worktree clean-up (owner rule: remove a worktree once it is no longer used).**
  - **Removed** (each merged, clean, nothing unpushed; branches remain on GitHub): app-backcache, app-carpage, app-followups, app-llm-parser, app-negation, app-parser, app-perf, app-projfix, app-uiux, kb-near-rule, kb-10i, and `~/Car_recommender_app/carrec-deploy`. The stale `main_before` entry was pruned.
  - **Kept:**
    - `kb-kbpipe` (this handover; others' uncommitted edits);
    - `recsys-v3` (its `.venv` is the Python for everything);
    - `app-rag` (an untracked `eval/results/rag_cache.json`, 109 cached RAG answers; awaiting the owner);
    - `kb-enrich-claude` (unmerged, no PR; pushed and clean; awaiting the owner).
  - #63 (PR K) was merged by the owner.
  - **Later, 28 Nov:** at the owner's request, `app-rag` and `kb-enrich-claude` were removed too.
    - The RAG cache from `app-rag` is saved at `~/carrec_saved/rag_cache_2026-11-22.json` (byte-identical copy, 109 answers).
    - Branch `kb/enrich-claude` is still on GitHub, unmerged.
    - Worktrees left: the main checkout, `kb-kbpipe` and `recsys-v3`.
- **28 Nov, old KB backups (owner: "Mac only"):** 82 files from `knowledge_base/backups/` and 3 old scratch copies were moved to `~/.Trash/CarRec_old_backups_2026-11-28/` (2.8 GB). Those were:
  - the KB backups from Sep 9 to Nov 22 and their -wal/-shm side files;
  - `scratch/carrec_kb_phase6_final_preproduction_backup.db`, `carrec_kb_pre_restore_forensic_snapshot.db` and `carrec_kb_production_backup.db`.
  - **Kept:**
    - the newest backup, `knowledge_base/backups/pre_update_ev_range_update_2026-11-22_20261122T072159Z.db` (the rollback point before the current prod state);
    - the frozen paper snapshot `~/carrec_kb_snapshots/carrec_kb_paper_v0_8592508.db`;
    - `scratch/carrec_kb_idemp.db`;
    - the Google Drive copy `~/My Drive/CarRec_backups/` (owner chose to keep it).
  - The backup names listed in CLAUDE.md now refer to files in the Trash. Once the Trash is emptied they are gone. Each phase's report and `KB_CHANGELOG.md` still describe what changed.
