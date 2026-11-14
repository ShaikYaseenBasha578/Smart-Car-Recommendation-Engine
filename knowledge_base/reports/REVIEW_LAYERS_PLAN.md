# Review layers plan: professional scores and owner ratings

Status: **waiting for owner approval** (14 Nov 2026). Nothing is built.
Surveys behind this plan: `REVIEW_LAYERS_SITE_SURVEY.md`, `REVIEW_LAYERS_ALTERNATIVES_SURVEY.md`.

## 1. What this adds

| Layer | Source | What is stored per model |
|---|---|---|
| Professional | Autocar India expert review page | Overall score and 7 aspect scores out of 10, review URL, page date |
| Owner | CarWale user-reviews page | Overall rating and 5 aspect ratings out of 5, number of ratings, URL, date read |

Both sources publish numbers. The tool reads the numbers; **no LLM writes or judges a score**, and no review text is stored.

Out of scope for now: Team-BHP (blocks automated reading), CarDekho expert scores (terms prohibit), YouTube, Reddit. Owner reliability and service-cost data has no source yet; see §9.

## 2. Decisions already made by the owner

- V1. Autocar India is accepted for the professional layer as a non-commercial, terms-grey source (its terms bar screen scraping; its robots file allows the pages). The risk is the owner's.
- V2. CarWale user ratings are accepted for the owner layer (terms silent, robots allow).
- V3. No permission emails. No source that blocks the fetch is ever worked around.
- V4. More depth and more sources come later; the design must make that cheap.

## 3. Schema (needs approval under P16)

The two tables approved earlier assumed LLM-written 1–5 ratings with quotes and forum themes. The sources we can actually use publish numeric scores, so the shape changes. This replaces the earlier `professional_assessment` definition (never applied) and adds `owner_rating`. `owner_theme` stays approved but unapplied, for a future forum-style source.

```sql
CREATE TABLE professional_assessment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id INTEGER NOT NULL REFERENCES model(id),
  source_id INTEGER NOT NULL REFERENCES source(id),
  source_aspect TEXT NOT NULL,          -- the publisher's own label, or 'overall'
  score REAL NOT NULL,
  scale_max REAL NOT NULL,              -- 10 for Autocar
  variant_scope TEXT,                   -- variant driven, if the page states it
  source_url TEXT NOT NULL,
  published_on TEXT,                    -- page date as shown
  observed_at TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'current' CHECK (status IN ('current','superseded','stale_generation')),
  CHECK (score >= 0 AND score <= scale_max),
  UNIQUE(model_id, source_id, source_aspect, observed_at)
);
CREATE TABLE owner_rating (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id INTEGER NOT NULL REFERENCES model(id),
  source_id INTEGER NOT NULL REFERENCES source(id),
  source_aspect TEXT NOT NULL,          -- the site's own label, or 'overall'
  score REAL NOT NULL,
  scale_max REAL NOT NULL,              -- 5 for CarWale
  rating_count INTEGER,                 -- ratings behind the score
  source_url TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'current' CHECK (status IN ('current','superseded')),
  CHECK (score >= 0 AND score <= scale_max),
  UNIQUE(model_id, source_id, source_aspect, observed_at)
);
```

Two new rows in `source` (Autocar India expert review; CarWale user ratings). No change to any existing table or view.

Rows are never deleted. A refresh that finds a changed score inserts a new row and marks the old one `superseded`, so history is kept.

## 4. How it runs

New command, same tool:

```bash
./bin/kbpipe reviews --no-write
```

Flags follow `kbpipe run`: `--only <model>`, `--max-models N`, `--no-write`, `--label`.

Steps per model:
1. **Find the page.** Autocar: `/cars/{make}/{model}/expert-reviews`. CarWale: `/{make}-cars/{model}/user-reviews/`. Slugs come from a small alias table in config, seeded from kbpipe's existing CarWale slugs.
2. **Fetch** with the existing `fetch.py`: cached, one request every 4 seconds per site, robots file checked first and obeyed. A block (403, 429, captcha) marks the model `unreachable` and moves on. No retries around a block.
3. **Check the page is the right car.** Make and model name on the page must match the requested model, as kbpipe already does for CarDekho. A wrong page is discarded.
4. **Parse the numbers.** One parser per source in `kbpipe/sources/` (`autocar_reviews.py`, `carwale_ratings.py`), reading structured data where the page has it and the visible score blocks otherwise.
5. **Validate.** Score within scale; expected aspect labels present; rating count is a positive integer. Anything odd leaves the model out and lists it in `flags.tsv`.
6. **Write** through the existing safe path: holder check, backup, history commit, staging copy, gates, one transaction, integrity check.

### Rules
- **Never fabricates.** No page, no numbers, no row. A model with no review stays empty.
- **Minimum evidence for owner ratings:** scores with fewer than 30 ratings are stored but exported with a low-confidence flag (see §6).
- **Old reviews.** If the KB knows the model was facelifted or replaced after the review's page date, the rows are stored as `stale_generation` and not exported. Where the KB has no launch date, the review is exported with its date shown.
- **Refresh:** pages older than 90 days are re-read on the next run.
- **Off switch.** `reviews.sources.autocar.enabled` in config. When false, Autocar is neither fetched nor exported. Removing its rows from the KB stays a manual owner decision.

## 5. Verification

No LLM extracts, so the checks are different from the spec pipeline:
- **Gates:** schema (re-pinned once after the migration), provenance (every row has URL, date and method), rows never dropped, every change in the apply log, idempotency re-run.
- **Independent re-check:** 15% of rows per source, at least 40, are re-fetched and the number is confirmed on the page by the existing verifier on the free Gemini/Groq chain. Bar: 98%, since these are plain numbers. Below the bar, that source is not written.
- **Human sheet:** 20 rows per source in `human_check.csv` for the owner.
- **Pilot first:** 10 models, no write, inspected before the full run.

## 6. Export and the recommender

Two files, written by the existing export script:

| File | Columns |
|---|---|
| `data/assessments.csv` | model, aspect, value (0–1), source, url, published_on, n_sources |
| `data/owner_ratings.csv` | model, aspect, value (0–1), rating_count, low_confidence, source, url, observed_at |

`aspect` here is the engine's fixed aspect. The mapping from each site's labels lives in one config table, so a label change is a one-line fix. One publisher label may feed two engine aspects (Autocar's performance-and-refinement score feeds `engine_performance` and `refinement`). Engine aspects with no source stay unknown.

Draft mapping, to be confirmed against real pages in the pilot:

| Source label | Engine aspect(s) |
|---|---|
| Autocar: performance and refinement | engine_performance, refinement |
| Autocar: ride and handling | ride_comfort, handling |
| Autocar: interior space and comfort | front_space, rear_seat_comfort |
| Autocar: mileage / efficiency | real_world_mileage |
| Autocar: features / equipment | features_tech |
| Autocar: value | value_for_money |
| Autocar: exterior design and engineering | build_quality (weak; may be dropped) |
| CarWale: comfort | owner comfort |
| CarWale: performance | owner performance |
| CarWale: fuel economy | owner real_world_mileage |
| CarWale: value for money | owner value |
| CarWale: overall | owner satisfaction |
| CarWale: exterior | not used |

Recommender changes (small, on `feat/recsys-v3`):
- `evidence.py` reads `owner_ratings.csv`; the owner sub-score uses ratings, with each score pulled toward the segment average in proportion to how few ratings it has (so 30 ratings move the score less than 700).
- The expert sub-score uses the 0–1 values. The thin-evidence rule (v3 design change 3) applies.
- Explanations cite the source and date: "Autocar India scores ride and handling 8/10 (review dated …)".
- Class weights (0.60 / 0.25 / 0.15) are re-tuned against the owner's 40 shortlists once data exists.

## 7. Policy notes for `CLAUDE.md`

- These rows are evidence classes PROFESSIONAL_ASSESSMENT and OWNER_REPORT. They never touch variant columns or `field_provenance`.
- P2 and P15 concern spec values and the old resolver; they do not apply to rating rows. This is stated in the kbpipe section.
- The app must show the source name and link wherever a score is shown.

## 8. Build order

1. **Page inspection (Sonnet, ~1 hour).** Fetch 3 models per site with kbpipe's fetcher, record exactly where the numbers sit, confirm the 7 Autocar labels. Report before any parser is written.
2. **Migration script** for the two tables and two source rows, run on a scratch copy; applied to prod only with the first real write.
3. **Parsers, command, validation, tests** using saved pages as fixtures.
4. **Pilot:** 10 models, `--no-write`. Owner sees the numbers.
5. **Full run** with write, verification and report.
6. **Export + recommender changes**, then re-run the evaluation and tune class weights.

Sonnet builds; Fable or Opus reviews steps 1, 4 and 6. No LLM quota is needed until the verification in step 5.

Done means: both tables filled for every model that has a page, verification at or above 98% per source, export files present, v3 tests pass, and an evaluation table before and after.

## 9. Adding depth later (V4)

Cheap by design:
- **Another source** = one parser file, one `source` row, some mapping lines. Tables, gates, export and engine are unchanged. `n_sources` already supports averaging several publishers.
- **Hand-entered rows** (for example the owner reading Team-BHP threads): a CSV with model, aspect, score, URL, imported by `kbpipe reviews --import <file>` with `extraction_method = 'manual_owner'`. Not in this build; about half a day when wanted.
- **Forum themes** (reliability, service cost, recurring faults): the approved `owner_theme` table is ready whenever a permitted source exists.

## 9a. Amendment (14 Nov 2026): text as well as numbers, and saved Team-BHP pages

Asked for by the owner after the first draft. Where this section differs from §1–§6, this section wins.

### Text from the two fetched sources
- **Autocar:** from the same page, the pros, cons and verdict are read by an LLM, which writes one short note per engine aspect **in our own words** (at most 25 words), plus an optional verbatim quote of at most 25 words. Stored in two new nullable columns on `professional_assessment`: `note TEXT`, `quote TEXT`.
- **CarWale written reviews:** an LLM reads the written user reviews the tool can reach for a model and fills the already approved `owner_theme` table: theme (reliability, service_cost, service_experience, real_world_mileage, build_issues, recurring_fault with a label, resale, satisfaction), direction, mentions, reviews sampled, up to 5 links. One added nullable column: `note TEXT` (our words, at most 25 words). `owner_theme` is therefore applied now, not shelved.
- A theme needs at least 3 mentions and at least 20 reviews sampled, or it is not written.
- No review text is stored beyond the 25-word quote. Nothing is shown in the app without the source name and link.

### Saved Team-BHP pages (owner-supplied, tool never contacts the site)
- The tool **never fetches Team-BHP**. No browser automation, no extension driven by the tool, no workaround of its block.
- The owner opens a thread in a normal browser and saves the page into `~/carrec_saved_pages/teambhp/`. Any file name works; the tool reads the model and thread URL from the saved page itself and asks when it cannot tell.
- `kbpipe reviews --import-saved <folder>` reads the local files and writes `owner_theme` rows with a new `source` row (Team-BHP, owner-saved pages) and `extraction_method = 'saved_page_llm'`. The saved files stay on the laptop and are never committed, exported or published.
- The owner reads Team-BHP's terms in a browser before using this. The terms risk is the owner's (same standing as V1).
- Helper: the tool writes `teambhp_links.html`, one search link per model, most popular first, so saving is click, save, next.

### LLM use and checks
- Extraction: free Gemini first, Groq fallback (the existing `extract` chain without Claude). About 600 calls for 92 models; one to two days of free quota. Runs resume where they stopped.
- Verification: a different model gets only the note or theme and the page text, and answers supported / not supported with the supporting line, which must be found in the page. Unsupported rows are dropped and logged. Sample: every note on the pilot, 25% after that. Bar: 95% supported, per source, or that source's text is not written (its numbers still are).
- Quotes are checked by exact substring match against the page.
- Haiku is not used as verifier.

### Export and recommender
- `data/assessments.csv` gains `note`, `quote`; `data/owner_themes.csv` is produced as in the recommender plan §3, plus `note`.
- Themes feed the owner sub-score (direction and share of mentions, shrunk by sample size) and the explanations: "Owners often mention high service cost (14 of 180 reviews, CarWale)".

### Build order change
Step 1 (page inspection) also establishes how many written reviews per model are reachable on CarWale. Text extraction is built after the numbers work end to end (new step 5a), so numbers are not held up by LLM quota.

## 10. Risks

- **Autocar terms.** Accepted by the owner (V1). Mitigations: robots obeyed, one page per model, off switch, source shown.
- **Page structure unknown.** The surveys could not see page source. Step 1 settles this before any parser exists.
- **Owner ratings are shallow and skew high** (most cars sit between 4.2 and 4.7). Scores are compared within a segment, which spreads them, but the layer will discriminate weakly. Do not expect a large jump in recommendation quality from it alone.
- **Model-level only.** A score applies to the whole model, not a variant or engine.
- **Coverage gaps** on new models; the engine already treats missing evidence as unknown.
