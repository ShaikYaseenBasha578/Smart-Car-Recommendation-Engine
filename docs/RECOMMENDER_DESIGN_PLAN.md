# Recommendation engine v3 — design plan (for approval; nothing built)

Date: 2026-11-14. Inputs: the code audit of the deployed engine (origin/main `ccb917d`) and a research scan, both done by Sonnet readers and not re-verified line by line.

## 1. Principles

1. **A stated must-have is never broken silently.** If it can't be met, the user is told which one and why.
2. **Unknown is unknown.** A blank value is never scored as "no" and never hidden.
3. **Code ranks, not a language model.** A model may help read the query. It never picks or orders cars.
4. **Every claim shown to the user comes from a field the engine used**, tagged by evidence class: spec, expert, owner.
5. **Measurable.** No change ships unless the evaluation set says it is not worse.
6. **Light enough for Render.** Plain Python and pandas, CSV files, no model weights in the app. Any LLM is reached over an API and is never required for a result.

## 2. Pipeline

```
query → parse → constraints + priorities → filter → (relax if empty) → score → diversify → explain
```

New code goes in `services/recsys/`, switched on by an environment variable (`RANKER=v3`). The current engine stays in place until v3 beats it on the evaluation set. Parser, filters and relaxation hints are kept and repaired, not rewritten.

## 3. KB contract (what the engine can rely on)

The app keeps reading exported files, not the database.

| File | Level | Contents | Source in KB |
|---|---|---|---|
| `data/catalogue.csv` | variant | Specs, features, price, safety stars, `unverified_fields` (exists today) | `v_variant_canonical_q` and the safety and warranty views |
| `data/assessments.csv` | model | One row per (model, aspect, source): rating 1–5, short quote, URL, date | new table `professional_assessment` |
| `data/owner_themes.csv` | model | One row per (model, theme): direction, mentions, posts sampled, sample URLs, period | new table `owner_theme` |

**Fixed aspect list (expert):** ride_comfort, handling, engine_performance, refinement, city_driveability, highway_stability, front_space, rear_seat_comfort, boot_practicality, real_world_mileage, build_quality, features_tech, value_for_money.

**Fixed theme list (owner):** reliability, service_cost, service_experience, real_world_mileage, build_issues, recurring_fault (with a short label), resale, satisfaction.

These lists are the contract. The review layers must produce exactly these; the engine consumes exactly these. Both files may be empty or partial and the engine must work.

### Proposed tables (need your approval under P16; no other schema change)

```sql
CREATE TABLE professional_assessment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id INTEGER NOT NULL REFERENCES model(id),
  aspect TEXT NOT NULL,                 -- one of the fixed aspect list
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  quote TEXT NOT NULL,                  -- at most 25 words, copied from the source
  variant_scope TEXT,                   -- variant(s) the reviewer drove, as stated; NULL if not stated
  source_id INTEGER NOT NULL REFERENCES source(id),
  source_url TEXT NOT NULL,
  published_on TEXT,
  extracted_at TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  UNIQUE(model_id, aspect, source_url)
);
CREATE TABLE owner_theme (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id INTEGER NOT NULL REFERENCES model(id),
  theme TEXT NOT NULL,                  -- one of the fixed theme list
  label TEXT,                           -- e.g. "clutch judder" for recurring_fault
  direction TEXT NOT NULL CHECK (direction IN ('positive','negative','mixed')),
  mentions INTEGER NOT NULL,
  posts_sampled INTEGER NOT NULL,
  period TEXT,                          -- e.g. "2025-01..2026-10"
  sample_urls TEXT NOT NULL,            -- JSON list, at most 5
  source_id INTEGER NOT NULL REFERENCES source(id),
  extracted_at TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  UNIQUE(model_id, theme, label, source_id)
);
```

Only ratings, short quotes, counts and links are stored. No article or post text.

## 4. Query understanding

Keep `intent_v2` (rules). Changes:

- **Negated features and makes become exclusions** ("no sunroof", "not Tata"). Today they are dropped.
- **Upper bounds are honoured** ("mileage under 30 km/kg").
- **The small classifier no longer sets hard filters.** Its guess for body type or fuel becomes a soft preference, shown to the user as "assumed", removable with one click.
- **Unsupported brand only** ("Mini Cooper"): say the brand isn't covered and stop; don't return an unrelated ranking.
- **Vague query** ("good car"): return a short prompt for budget and use, plus a neutral shortlist labelled as such.

**LLM parser (on).** Called when the rules leave part of the query unexplained. Gemini free tier, over HTTPS.

- **Structured output:** the model must return JSON matching a typed schema (the same vocabulary the rules use). Anything that fails validation is discarded.
- **Grounding rule:** a hard constraint from the model is accepted only if it quotes the words in the query that state it. Otherwise it becomes a soft preference shown as "assumed".
- **Fallback:** two-second timeout; on timeout, quota or error the engine continues on rules alone. A daily call cap keeps it inside the free tier.
- **Caching:** per normalised query.
- **Logging:** for every query, whether the LLM was called, latency, tokens, whether the result was accepted, and why it fell back. This feeds a small stats endpoint.
- **Evaluation:** the query set is run with the LLM on and off; the comparison is reported. If the LLM makes results worse, it is switched off by an environment variable.

**Priorities.** Each query yields weights over the criteria in §5, from the use case and phrases ("for my parents" raises comfort and ease of driving; "highway" raises stability and performance). The weights are returned with the results and shown as chips the user can switch.

## 5. Scoring (multi-criteria, replaces `ranking_engine.py`)

Each candidate gets a value from 0 to 1, or *unknown*, on each criterion:

| Criterion | From |
|---|---|
| value_for_budget | price against the stated budget and against same-segment cars |
| safety | airbags, ESC, crash-test stars (unrated = unknown) |
| running_cost | mileage or range for its fuel type; never compared across fuel types on raw numbers |
| comfort_features | climate control, rear vents, sunroof, ventilated seats, cruise control and similar |
| space_practicality | seats, boot, wheelbase, ground clearance |
| performance | power-to-weight, torque, gearbox type |
| tech_assist | ADAS, 360 camera, connected features, wireless charging |
| expert_* | mean rating per aspect from `assessments.csv` |
| owner_* | direction and share of mentions per theme from `owner_themes.csv` |

Rules:

- **Scales are relative to the candidates' segment**, not hand-set point values.
- **Overall score = weighted mean over the criteria that are known**, multiplied by a mild coverage factor: `1 − 0.15 × (weight of unknown criteria)`. A car with gaps is ranked slightly lower, not last.
- **Three sub-scores are kept and shown: spec, expert, owner.** The overall rank uses default class weights of 0.60 / 0.25 / 0.15, renormalised when a class has no data for that car. These three numbers are the only tuning knobs between facts and opinions.
- **No model-name lists, no brand bonuses.**
- **A required feature that is unknown** keeps the car in, flagged, with that feature counted as unknown in the coverage factor.
- Every number that enters the score is kept, so the explanation can cite it.

## 6. When nothing fits

1. Say so.
2. Compute the smallest relaxations that give results, trying single constraints and pairs, ordered by how little they give up (budget by the smallest amount first; features before body type; body type before fuel).
3. Show the nearest cars under the best relaxation, each labelled with the constraint it breaks and by how much ("₹40,000 over budget").

Nothing is relaxed without being named.

## 7. Diversity

- One variant per model: the best-scoring variant inside the constraints (today it is the lowest id, usually the base trim).
- Then a standard re-ranking (MMR) across models on make, body type and price band, so the list is not eight near-identical cars. Disabled when the user names a make or model.

## 8. Explanations

Built by templates from the values used in scoring. No generated prose.

- Up to four reasons per car, each tagged *spec*, *expert* or *owner*, each with its source link available.
- "Unknown" items are listed plainly ("crash rating: not tested yet").
- The match badge shows the overall score with its coverage ("Strong match · 2 things unknown") and replaces today's "Great match".

## 9. Evaluation (built first)

`eval/queries.jsonl`, about 200 queries: English and Hinglish, lakh and crore phrasing, negations, ranges, vague, over-constrained, unsupported brand, and paraphrase groups.

| Metric | Target |
|---|---|
| Constraint satisfaction (every returned car meets every stated hard constraint, checked against the catalogue) | 100% |
| Parse accuracy against labelled intent | reported per field |
| Paraphrase and Hinglish consistency (same top results for the same need) | reported; must not fall |
| "Nothing fits" handled as §6 | 100% |
| Unknown handling (planted blanks never scored as "no") | 100% |
| Shortlist agreement on 40 queries you label (which 5 cars a knowledgeable friend would suggest) | v3 at least as good as today's engine |

One command runs it and prints a table. No LLM judge.

## 10. Service, deployment and CI

**API (FastAPI).** The v3 recommender is exposed as a small typed service, separate from the existing Flask pages:

- `POST /api/v3/recommend`: query in; parsed intent, weights, ranked cars with sub-scores, reasons and relaxations out.
- `GET /api/v3/car/{make}/{model}`: evidence for one model by class.
- `GET /api/v3/stats`: LLM call rate, fallback rate, latency.
- Request and response shapes are typed models, so the API documents itself.
- The Flask app keeps serving the pages and calls the v3 functions directly. Both share one code path in `services/recsys/`; FastAPI is a second way in, not a rewrite of the site.

**Docker.** One Dockerfile that runs the app. Render can deploy from it, and the same image runs on Azure Container Apps or any other host. Moving or adding a deployment becomes a configuration step.

**CI (GitHub Actions).** On every pull request: the test suite, then the evaluation set. The evaluation table is posted on the pull request; a drop in constraint satisfaction fails the check.

**Render specifics.**

- No new heavy dependency: no embedding model, no ML runtime. The unused KNN pickle, the unwired semantic reranker and the legacy parser path are removed.
- Data is loaded once at start from the CSV files.
- The LLM key lives in a Render environment variable.
- The catalogue export is updated to the current KB (its fixed 832-row check goes) and gains the two new files.
- All of this lands through pull requests; I don't merge, and `main` deploys only when you merge.

**Azure (optional).** A second deployment from the same image, once Docker exists. No technical reason to leave Render; this is for showing the app runs on a major cloud.

## 10a. Advisor (conversation on top of v3)

A chat layer in which an LLM talks to the user and calls the engine as tools. It never picks or orders cars itself.

| Tool | What it does |
|---|---|
| `recommend(constraints, priorities)` | Runs the v3 engine |
| `explain(car, query)` | Returns the reasons and sub-scores the engine produced |
| `compare(cars)` | Returns a field-by-field comparison from the catalogue |
| `evidence(model, aspect)` | Returns expert quotes and owner themes with links, when they exist |

Rules:

- Every car and every fact in a reply must come from a tool result in that conversation; the reply is checked against the tool results before it is shown, and anything unsupported is removed.
- The advisor may ask one clarifying question when the request is vague.
- It is evaluated the same way as the engine: scripted conversations, with constraint satisfaction checked against the catalogue.
- When the review layers have data, `evidence` gives retrieval with citations ("what do owners say about the clutch?").

This is built after v3 passes its evaluation. If it doesn't fit before November 16, this section is its plan.

## 11. Build order

| Step | What | Who |
|---|---|---|
| 1 | Evaluation set and runner; baseline numbers for today's engine | Sonnet drafts, you label 40 shortlists, I review |
| 2 | Parser repairs (§4) | Sonnet |
| 3 | Scoring, relaxation, diversity (§5–7) | Sonnet builds from this plan, I review |
| 4 | Explanations and API fields (§8); small front-end change to show them | Sonnet |
| 5 | Export update and the two empty contract files | Sonnet |
| 6 | Compare v3 against baseline; adjust | Me |
| 7 | LLM parser with structured output, caching and logging (§4) | Sonnet |
| 8 | Dockerfile and CI workflow (§10) | Sonnet |
| 9 | FastAPI endpoints over `services/recsys/` (§10) | Sonnet |
| 10 | Advisor with tool calling (§10a) | Sonnet builds, I review; may fall after Nov 16 |
| Later | Tune class weights once real review data exists; optional Azure deployment | After Nov 16 |

## 12. Decisions for you

| # | Decision | My default |
|---|---|---|
| R1 | LLM parser in the query path | **Decided: on**, with structured output, fallback to rules, and an off switch if the evaluation shows it hurts |
| R2 | Priorities | Inferred from the query and shown as switchable chips |
| R3 | Facts and opinions | Three visible sub-scores, one overall rank |
| R4 | Nothing fits | Show nearest cars with the broken constraint named |
| R5 | Conversation | **Decided:** one query, one answer in v3, then the tool-calling advisor on top (§10a) |
| R6 | The two tables in §3 | Approve as written |
| R7 | Class weights 0.60 / 0.25 / 0.15 | Start here, tune later |
| R8 | FastAPI, Docker, CI | **Decided:** added (§10) |
