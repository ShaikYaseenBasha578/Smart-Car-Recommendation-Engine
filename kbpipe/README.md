# kbpipe

Keeps the CarRec knowledge base (`knowledge_base/carrec_kb.db`) complete and current. It runs from a terminal, without Claude Code, on free LLM tiers.

One run does five things:

1. **Discovery.** Reads the brand pages of CarWale and CarDekho and compares them with the KB: new models, new variants, models and variants no longer listed, changed prices and specs.
2. **Extraction.** Reads the structured data both sites embed in their pages. No LLM is used for this. Every value keeps its URL, fetch time and method.
3. **Reconciliation.** Applies the precedence rule and logs every disagreement.
4. **Verification.** A separate step sends sampled values back to their sources and asks a different model whether the source supports them.
5. **Gates and report.** Four scripted checks decide whether the staged changes reach the KB. Then it writes the summary and the review file.

## Setup

```bash
cd ~/carrec_worktrees/kb-kbpipe
```

```bash
./bin/kbpipe status
```

The first call creates a virtualenv (`.venv-kbpipe/`) and installs two packages: PyMuPDF and pytest. Everything else is the Python standard library.

Set the API keys in your shell profile. They are read from the environment and never stored:

```bash
export GEMINI_API_KEY=...   # free tier
```

```bash
export GROQ_API_KEY=...     # free tier, used as fallback
```

To call it as `kbpipe` from anywhere:

```bash
ln -s ~/carrec_worktrees/kb-kbpipe/bin/kbpipe /usr/local/bin/kbpipe
```

## Commands

| Command | What it does |
|---|---|
| `kbpipe run` | The whole pipeline. Incremental: only models whose listing changed are processed. |
| `kbpipe run --full` | Re-process every model and run the full audit. |
| `kbpipe run --no-write` | Do everything except touch the KB. Use this to look first. |
| `kbpipe run --only Punch --only Nexon` | Limit the run to named models. |
| `kbpipe run --max-models 10` | Stop after 10 models; the rest wait for the next run. |
| `kbpipe run --audit full\|changed\|none` | Scope of the final audit. Default: `full` on the first run and with `--full`, otherwise `changed`. |
| `kbpipe apply-review <REVIEW file>` | Apply the review items you ticked. |
| `kbpipe agreement <human_check.csv>` | Your agreement with the verifier, from the sheet you filled in. |
| `kbpipe reviews` | Review layers: Autocar India expert scores (out of 10), CarWale owner ratings (out of 5), short notes and owner themes. See below. |
| `kbpipe status` | KB hash, whether anything holds the file, recent runs. |

Tests:

```bash
.venv-kbpipe/bin/python -m pytest kbpipe/tests -q
```

## What a run writes

Everything goes to `knowledge_base/runs/<date>/`:

| File | Contents |
|---|---|
| `RUN_SUMMARY.md` | The report. Every number names the file it came from. |
| `REVIEW_<date>.md` | Only what needs you. |
| `human_check.csv` | 30 audited values with a blank column for your verdict. |
| `verify/results.jsonl` | The verifier's verdicts. Read-only. The accuracy numbers come from this file alone. |
| `conflicts.tsv` | Every disagreement between sources and how it was resolved. |
| `flags.tsv` | Every cell left blank and why. |
| `links.tsv` | Which CarWale version was linked to which CarDekho variant and which KB variant. |
| `changeset.json` | Exactly what was applied. |
| `pending.json` | The changes behind each review item. |
| `apply_log.tsv` | Every row inserted or updated. |
| `run.json`, `run.log` | Machine-readable result and the log. |

## How to read the report

- **Coverage** is counted from the database before and after.
- **Verification** gives accuracy as match ÷ (match + mismatch). "Unreachable" (the source could not be fetched, or no longer states the field) and "verifier errors" (no usable reply, or evidence that is not in the source) are listed beside it and never counted as matches.
- **Source classes**: `brochure` (OEM PDF, cited by page), `aggregator` (CarWale or CarDekho page), `legacy` (values from the June 2026 import, which recorded no URL; they are checked against the current page for that variant, so a mismatch can also mean the car changed since June).
- **Below the bar** lists any field type under 95%. If a field type falls below the bar during a run, extraction of that type stops and its new values are not written.
- **Gates** must all pass, or nothing is merged.

## Review

Open `REVIEW_<date>.md`. Each item with changes behind it has two boxes:

```
- [ ] approve R001  (applies 46 change(s))
- [ ] reject R001
```

Put an `x` in one, save, and run:

```bash
kbpipe apply-review knowledge_base/runs/<date>/REVIEW_<date>.md
```

Approved items go through the same backup, staging, gates and write path as a run. Unticked items stay pending. Items with no boxes (a facelift, a model on one site only) need a decision the tool cannot turn into a change by itself.

What always goes to review and is never applied by itself:

- any value on an existing variant that both sites agree on but that differs from the KB, including prices;
- blanks on existing variants that both sites could fill;
- a new variant in a held model, or one that looks like a rename of a variant the KB has;
- KB variants and models no longer listed (nothing is ever deleted; approval marks them discontinued);
- models whose launch date is newer than the KB's data for them (facelift or new generation);
- models listed on one site only.

## Rules the tool follows

- **Never fabricates.** A value is written only when two sites agree on it for the same variant, or an OEM brochure states it. One site alone decides nothing; the cell stays blank and is listed in `flags.tsv`.
- **Precedence:** OEM brochure, then two agreeing aggregators. Journalist sources are not used.
- **Existing values are not changed by aggregators.** When both sites agree with the KB, that is recorded as confirming evidence with URLs.
- **Linking is strict.** A CarWale version and a CarDekho variant are linked only when fuel, gearbox class and trim words are equal, and the ex-showroom prices match within 0.5%. A page that turns out to show a different variant than requested is discarded.
- **Editions are skipped.**
- **Safe write:** holder check, hash check, backup, staging copy, four gates, idempotency re-run, one transaction, integrity check, prod compared with staging table for table. Before every write the KB is dumped to a local git repository (`~/carrec_kb_history`, no remote) and tagged `kb-run-<date>`.
- It never touches the app repository's `main`, any remote, or the deploy.

## Configuration

Defaults are in `kbpipe/config.py`. To override, create `kbpipe.config.json` in the repo root with only the keys you want to change. Useful ones:

| Key | Default | Meaning |
|---|---|---|
| `scope_makes` | the 12 makes in the KB | Makes covered. |
| `scope_max_base_price` | 5000000 | Models whose cheapest variant costs more are out of scope. |
| `max_new_models_per_run` | 40 | Cap on new models per run. |
| `held_models` | Seltos, Brezza, Baleno, WagonR, Jimny, Kylaq | Every change to these goes to review. |
| `refresh_days` | listing 0.5, model_page 1, spec 90 | How old a cached page may be before it is fetched again. |
| `min_seconds_between_requests` | 4 | Politeness delay per site. |
| `audit_per_stratum` | 25 | Audit sample per (field type × source class). |
| `verify_bar` | 0.95 | Accuracy bar. |
| `llm` | Gemini first, Groq fallback | Backends per role. See below. |
| `model_aliases` | {} | Listing name → KB name, for models the sites spell differently. |

### LLM backends

Each role (`extract`, `verify`, `verify_image`) lists backends in order; the next is used when one runs out of quota. Kinds: `gemini`, `openai` (any OpenAI-compatible endpoint, such as Groq), `ollama` (local), `claude_cli` (optional, not free). Model names change; if a model is retired the run log says so and you edit the `model` in your config. Each backend has a `daily_calls` budget so a run stops cleanly before the provider cuts it off; the audit then resumes on the next run.

## When something breaks

| Symptom | What it means | What to do |
|---|---|---|
| "brand page … could not be read" | A site changed its page format or blocked the request. Affected models are marked UNKNOWN and nothing about them is written. | Open the URL in a browser. If the page loads, the embedded JSON moved: the parsers are `kbpipe/sources/carwale.py` and `cardekho.py`, each about 150 lines. |
| Many "VARIANT_NOT_ADDED" | The two sites name or price variants differently, so they were not linked. | Read `links.tsv`. Nothing wrong is written; coverage is lower. |
| "KB is held by …" or "non-empty -wal" | Another program has the database open. | Close it and run again. The tool will not work around it. |
| "gates failed on staging" | A check failed. The KB was not touched. | The summary names the gate and the row. |
| "daily call budget reached" | The free tier ran out. | Run again tomorrow; finished verdicts are kept. |
| A field type is below 95% | The mapping for that field is probably wrong for some make. | Look at the mismatches in `verify/results.jsonl`, fix the mapping, rerun with `--full --only <model>`. |

To undo a write, restore the backup named in the summary (`knowledge_base/backups/pre_kbpipe_…db`) over the KB. Do that by hand and deliberately; the tool has no command for it.

## Limits you should know

- Dimensions, boot space, fuel tank, ABS and ESC come from CarDekho only, because CarWale's model page does not carry them per variant. Under the two-site rule they stay blank on new variants until a brochure or a third site supplies them.
- Brochure extraction for new models is not part of this version. Brochure-backed values already in the KB are audited (the verifier renders the cited page).
- Aggregators copy from each other, so "two sites agree" is weaker than two independent sources. Values accepted this way are tagged `AGGREGATOR_AGREED_UNVERIFIED`.
- The site terms of use have not been reviewed. The tool fetches public pages at one request every four seconds per site and caches them.


## Review layers (`kbpipe reviews`)

Plan: `knowledge_base/reports/REVIEW_LAYERS_PLAN.md` (section 9a wins). Page findings: `knowledge_base/reports/kbpipe/REVIEW_PAGE_INSPECTION.md`.

```bash
./bin/kbpipe reviews --no-write --label reviews_pilot --only "Hyundai Creta" --only "Tata Nexon" --verify-all
```

| Flag | Meaning |
|---|---|
| `--only NAME` | A model name or `Make Model` (repeatable). |
| `--max-models N` | Stop after N models (most variants first). |
| `--no-write` | Stage and gate on a scratch copy; the KB is not touched. A missing review schema is added to the copy only. |
| `--no-text` | Numbers only; no LLM calls. |
| `--verify-all` | Check every note and theme (default: a fixed 25% of models, the same ones every run; the pilot uses all). |
| `--write-only` | Only warm the writer cache (Sonnet). The checker is not called and no text is kept. Run the same command without it later to do the checks. |
| `--force` | Ignore the 90-day freshness of rows already in the KB. Use it to add text to rows that hold only numbers; pages and LLM answers come from the caches. |
| `--label NAME` | Run folder `knowledge_base/runs/<label>/`: `RUN_SUMMARY.md`, `reviews_rows.tsv`, `flags.tsv`, `changeset.json`, `run.log`. |
| `--import-saved FOLDER` | Read Team-BHP pages you saved in a browser (local files only, nothing is fetched) into `owner_theme`. |
| `--teambhp-links` | Write `teambhp_links.html` (one search link per model, most popular first). Fetches nothing. |

How it works:
- Fetching goes through `Fetcher.get_polite`: robots.txt is read first and obeyed, one request per 4 s per site, cached, one attempt only. A 403, 429 or captcha is recorded in `flags.tsv` and the model is skipped; there is no retry around a block. Only autocarindia.com and carwale.com are contacted; Team-BHP never.
- Numbers come from the pages by parsers (`sources/autocar_reviews.py`, `sources/carwale_ratings.py`); no LLM writes a score. The page must be for the requested make and model, scores must be in range, and all seven aspect labels must be present, or the model is left out and flagged.
- Text (`kbpipe/review_text.py`): **Claude Sonnet writes** (`llm.reviews_write`, the subscription, one call per model for Autocar; CarWale reviews in chunks, the 60 newest of the first six pages, ids as the recency proxy) and **the free Gemini then Groq chain checks** (`llm.reviews_check`, one call per model per source carrying all claims). Writer and checker must be different backends and models; Haiku is refused; the checker chain never falls back to the writer. Autocar notes: at most 25 words, own words, one aspect, optional quote of at most 25 words that must be an exact substring of the page text. CarWale themes: at least 3 mentions in at least 20 reviews sampled; the checker lists the reviews that support each theme with a line copied from each, and the stored `mentions` is the number it confirmed. A checker verdict counts only if its supporting line is a substring of the page text. Below 95% supported per source, that source's text is not written; its numbers still are.
- Numbers re-check (plan section 5): for 15% of models per source (at least 15, so all in a small run) the checker confirms each stored score on the page text; `numbers_check.jsonl`. Below 98% the source's numbers are not written.
- Cache: every writer and checker answer is stored in `~/carrec_kb_cache/review_llm/` keyed by model, source, hash of the text sent and prompt version. An unchanged page costs no call on a rerun or on the write run (`RUN_SUMMARY.md` shows calls made and cache hits). `llm_calls.jsonl` lists only real calls.
- Audit: `text_audit.jsonl` has every note and theme, kept or dropped, with claim, checker verdict, supporting line and drop reason.
- Free-tier limits seen on 2026-11-15: Gemini flash-lite 500 requests a day (resets about 08:00 UTC); Groq gpt-oss-120b 8,000 tokens a minute, 200,000 tokens a day (rolling). Roughly 250 checker calls cover a full run, so one day of Gemini is enough; Groq alone is not. A run that finds both empty stops cleanly (nothing is lost).
- Order of a full text run: `--write-only` (Sonnet only, cache warmed), then the same command without it (checks), then the write run with the same flags, which makes no new calls.
- Quota: if the Sonnet subscription limit or all the free checker quota runs out, the run stops text cleanly, lists the models not reached in `RUN_SUMMARY.md`, and a rerun resumes from the cache. It never switches writers.
- Autocar slugs: aliases and the models with no expert review of their own are in `reviews.autocar_slugs`, `reviews.autocar_page_names`, `reviews.autocar_no_review` (config.py). Autocar redirects a retired page with HTTP 308; kbpipe does not follow it, it records it.
- Rows are refreshed after 90 days (`reviews.refresh_days`). A changed score inserts a new row and marks the old one `superseded`; nothing is deleted.
- Off switch: `reviews.sources.autocar.enabled` (false: Autocar is neither fetched nor written).
- Writing needs the tables from `kbpipe/migrations/reviews_tables.py`, which creates `professional_assessment`, `owner_rating`, `owner_theme` and three `source` rows. It is DDL, so the owner approves it (P16) and runs it with `--prod` once; it refuses the production file otherwise. `reviews` refuses to write while the production KB lacks the tables, and the schema pin (`kbpipe pin-schema`) must be refreshed after the migration.
- Team-BHP: save a thread in your browser into `~/carrec_saved_pages/teambhp/`, then `kbpipe reviews --import-saved ~/carrec_saved_pages/teambhp --no-write`. The model and thread URL are read from the saved page (a `saved from url` comment, the canonical link or the title); an unknown model is asked for. The saved files stay local and are never committed or exported. Read Team-BHP's terms in a browser first; that risk is yours.

## Brochure layer for models already in the KB (13 Nov 2026 additions)

Official brochures for the 30 models kbpipe added on 13 Nov 2026 are downloaded into `oem_new_dir` (`knowledge_base/sources/oem_kbpipe`, never `sources/oem`) by:

```bash
.venv-kbpipe/bin/python -m kbpipe.tools.brochure_acquire
```

URLs are in `kbpipe/data/brochure_urls_new_models.json` (each found on the maker's own brochure or model page). robots.txt is obeyed, one attempt per URL, no retry around a block; a host whose robots.txt answers 404 has no rules. URL, date and hashes go to `oem_new_dir/brochure_manifest.json`. A KB model with no brochure in `sources/oem` uses the `oem_kbpipe` manifest (`brochure.locate_new_dir`).

Reading and checking (all in `kbpipe/brochure.py`):
- Reader: `llm.brochure_read` = Claude Sonnet only. No fallback to a free model; a usage limit or 3 consecutive failed calls stop the run (`incomplete` in the model's brochure summary) and a rerun resumes from the cache.
- Checker: `llm.brochure_check` = Opus first, then the Gemini image backend. It sees the rendered page and is asked, per cell, supported / not_supported / unclear. Only supported cells are attached. A checker is never the backend that read the page (the reader's backend is removed from the chain; a violation raises). Features: 1 needs a fitted marker for that trim; 0 needs an explicit absence marker; an unmarked blank is `unclear`.
- Cache: reader answers in `<cache_dir>/brochure_reads`, checker answers in `<cache_dir>/brochure_checks` keyed by (PDF SHA-1, page, prompt version, claims). A rerun, including the write run, makes no new LLM call. `brochure.check_prompt_version` must be bumped if the checker prompt changes.
- `brochure.check_fraction` (default 1.0 = every cell). Below 1, a fixed sample per (model, field group) is checked, and unchecked cells of a group are attached only if its sample is at least `check_bar` (0.95) supported.
- Report: `python -m kbpipe.tools.brochure_report <run_dir>` writes `BROCHURE_REPORT.md`, `brochure_cells.tsv` (every cell with verdict and the checker's evidence) and `brochure_disagreements.tsv`.

Dry run of the 30 models:

```bash
./bin/kbpipe run --no-write --full --no-verify --only Alcazar --only Sonet ... --label brochure_new_models_2026-11-15
```
