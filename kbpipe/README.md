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
