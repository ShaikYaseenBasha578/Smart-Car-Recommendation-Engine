# Plan: LLM parser, ML in ranking, grounded (RAG) explanations — 22 Nov 2026, awaiting owner approval

Three pieces of app work on `main` of the app repository. Each one ships as its own pull request, which the owner merges. Opus designs and reviews; Sonnet subagents write the code in their own worktree and branch. Tests run from `tests/` only. The impeccable skill is used for any UI change, and every pull request with a visible change carries screenshots.

**Fixed rule for all three:** hard requirements (budget, fuel, gearbox, body, seats, features, minimums, exclusions) stay rule-parsed and rule-checked. No model may add, remove or loosen a hard filter unless it quotes the query's words for it (the existing LLM-parser rule). Every pull request must keep "no requirement violated" at 193/193 (main) and 105/107 (held-out), and must not lower "every requirement verified".

**Suggested order:** A, then B1, then C, then B2. B3 comes last, and only if the site gets real traffic. A comes first because it is cheap, and because C reuses its provider, pacing and cache code.

---

## A. Make the LLM parser measurable, then decide on/off

**Why it is off today.** It works, but both evaluation runs were starved by free-tier rate limits (`eval/results/heldout_v3_llm*.json`).
- 62 of 210 held-out queries reached the LLM.
- 40 Gemini calls and 52 Groq calls fell back on quota or 429 errors.
- One constraint was accepted. Most answers repeated what the rules had already found.

So there is no valid measurement yet, and only 30% of the queries even exercise it.

**Steps**
1. **Pacing in the provider client** (`services/recsys/llm_parse.py`):
   - A token bucket set by `LLM_PARSER_RPM`, defaulting to the provider's free per-minute limit.
   - On a 429, honour `Retry-After` and set a cool-down, so no further calls go out until it ends. The request still answers from the rules at once, as it does now.
   - The existing daily cap stays.
2. **Resumable, paced evaluation runs** (`eval/run_eval.py --llm on`):
   - Use the existing on-disk answer cache.
   - Wait between calls, and resume where a run stopped.
   - A full held-out run (62 calls) then takes about 5 minutes and stays inside the free tier.
3. **A "hard queries" set** (`eval/hard_queries.jsonl`, about 40 queries):
   - Phrasings the rules do not cover: unusual Hinglish, indirect limits ("my garage is 4 m long", "can't spend more than my 9 lakh loan"), multi-clause requests.
   - Labels are written and frozen before any LLM run. The owner writes or approves them; generated drafts are allowed but hand-checked.
4. **Measure, with the LLM on and off,** on main, held-out and hard:
   - violations and verified share;
   - parse accuracy per field;
   - queries improved or worsened;
   - fallback rate;
   - p95 latency.
5. **Decision gate:** turn it on in production only if all of these hold:
   - no set loses a zero-violation query;
   - at least 5 hard queries improve and none get worse;
   - the fallback rate is under 5% at the paced rate;
   - p95 latency stays within the 2-second budget.

   The owner sets `LLM_PARSER=on` and the key in Render's environment; Claude never handles the key.

**Cost:** free tier only. **Size:** one pull request (about 2 Sonnet tasks), plus the owner's label check.
**Risk:** low. Every failure already falls back to the rules.

---

## B. ML in the ranking

### B1. Learn the scoring weights from the shortlists (first ML step)

**What is learned:** about 8 constants in `services/recsys/config.py` that today are set by hand:
- `CLASS_WEIGHTS` (spec, expert, owner)
- `COVERAGE_PENALTY`
- `MMR_LAMBDA`
- `EXPERT_SOURCE_K`
- `OWNER_SAMPLE_K`
- `BLANK_PRIOR_MARGIN`
- `PRICE_DEFAULT_WEIGHT`
- `REQUIRED_ITEM_WEIGHT`

**The data limit:** only 40 hand-made shortlists (`eval/shortlist_sheet.csv`), which is too few to tune without overfitting. **Owner step:** fill 60 more queries with the same blind instructions (`eval/SHORTLIST_INSTRUCTIONS.md`) to reach 100. The new queries are drafted first and frozen before the owner sees any engine output.

**Steps**
1. Expose these constants as one parameter object, so the evaluation can pass a candidate set without editing `config.py`. Production behaviour is unchanged.
2. **Search:** a seeded random search plus local refinement over bounded ranges. No new heavy dependency.
   - Objective: mean recall@8 + MRR.
   - Hard constraint: violations and verified share unchanged on main and held-out.
3. **Honest estimate:**
   - 5-fold cross-validation over the shortlists, with the folds fixed in advance.
   - Report the gain per fold and a bootstrap 95% interval.
   - Keep 20 shortlists out of the search entirely as a final test.
4. **Adopt only if** the interval on the held-out shortlists excludes zero and no hard metric drops. Otherwise report "no reliable gain" and keep the hand-set weights. That is still a paper result.
5. The pull request carries the new constants, the report (`eval/results/weights_*.json` plus a markdown summary), the regenerated golden files and the updated README evaluation table.

**Cost:** local CPU only. **Size:** one pull request (2–3 Sonnet tasks), plus the owner's 60 shortlists.

### B2. Embeddings for soft preferences and "something like X"

**What changes:** soft phrases such as "comfortable on long trips", "good for my parents" or "fun to drive" are currently matched with keyword lists. A small sentence-embedding model maps the unexplained phrase to the review aspects and criteria it is closest to, and those weights are raised. It only changes soft weights, never filters. "Something like Creta" also uses embedding similarity of the cars' review notes, alongside make, body and price.

**Model:** a multilingual MiniLM-class model (Hinglish matters), exported to quantized ONNX (about 25–50 MB) and run with `onnxruntime`. It has to fit Render's free 512 MB, so peak memory is measured first. If it does not fit, fall back to precomputed phrase-to-aspect tables built offline.

**Steps**
1. Offline: embed every aspect description and every stored review note and quote at export time, and store the vectors beside the catalogue.
2. At request time: embed only the residual soft phrase, then take the top aspects above a similarity threshold. The explanation names the phrase it matched ("read 'long trips' as ride comfort").
3. **Evaluation:** add about 30 soft-preference queries with frozen aspect labels.
   - Measure the aspect-match precision. Keep the threshold where precision is at least 90%.
   - Check shortlist recall@8.
   - Violations must not change.
4. A blind check of the phrase-to-aspect matches on a stratified sample by a fresh agent (P12-style, at least 95% agreement), because the matcher decides more than 20 cases.

**Cost:** free; a one-off model download. **Size:** one pull request (3 Sonnet tasks).

### B3. Learning to rank from real user behaviour (only with traffic)

**What it needs:** anonymous interaction logs (results shown, card clicks, car-page opens, comparisons) and enough of them, roughly a few thousand sessions. The demo may never get there; this plan says so plainly.

**Steps, if approved later**
1. **Logging, with a privacy notice on the page:**
   - a random session id, no IP and no account;
   - the query text only after the notice is shown;
   - 90-day retention.

   Render's free tier has no persistent disk, so this needs a small external store. That is an owner decision (and possibly a cost).
2. Small position randomisation (occasionally swapping results 2 and 3) so the clicks can be corrected for position bias.
3. Train LightGBM LambdaMART on features the engine already computes: sub-scores, criteria values, coverage and price fit. Hard filters stay as they are.
4. Offline replay evaluation, then a 50/50 A/B test, before any switch.

**Decision now:** plan only. Revisit when traffic exists.

---

## C. Grounded (RAG) explanations

**What changes:** today each car's reasons come from templates. With C:
- **Retrieval:** for each recommended car, gather the facts the score already used: spec cells with their sources, expert notes and quotes with URLs, owner themes with counts, and the Bharat NCAP row if one exists.
- **Generation:** one LLM call per query, covering all shown cars, writes 2–3 plain sentences per car. Each sentence cites the fact ids it uses, e.g. `[f3]`.
- **Verification:** a deterministic checker, pure Python, decides whether the text may be shown:
  - every number in the text, with its unit, must appear in the cited facts;
  - every car or model name must match the car;
  - every sentence must cite only fact ids from the provided set;
  - safety claims must come only from the NCAP row;
  - no superlatives that compare against other cars unless the facts compare them.

  If any check fails, the card shows the template explanation instead. The request never waits more than the time budget.

**Steps**
1. **Fact retrieval** (`services/recsys/facts.py`): builds the per-car fact list with ids and sources from the score's own inputs. This is deterministic and tested.
2. **Generator and checker** (`services/recsys/rag_explain.py`): reuses A's provider, pacing and cache. The cache key is the car ids plus the intent hash. The checker is unit-tested with crafted bad outputs: wrong numbers, invented features, a missing citation.
3. **UI** (impeccable skill):
   - Citations render as small numbered links to the source.
   - An unobtrusive "written by AI from the sources below" label.
   - The template fallback looks the same minus that label.
   - Screenshots go in the pull request.
4. **Evaluation:**
   - The checker's pass rate over main plus held-out (target at least 95%; failures fall back, but a low rate means the prompt needs work).
   - A blind groundedness check of 50 shown explanations by a fresh agent and by the owner. Each sentence is marked supported, unsupported or wrong.
   - The bar: 0 wrong and at most 2% unsupported, against the facts list.
5. Off by default behind `RAG_EXPLAIN=on`, like the parser. The owner enables it after reading the evaluation.

**Later, optional:** "Ask about this car" on car pages, answering only from that car's facts and review notes (BM25, or B2's embeddings, over the stored notes), with the same checker and "Not in our sources" when nothing supports an answer.

**Cost:** free tier with the daily cap; one call per query, cached. **Size:** one or two pull requests (4 Sonnet tasks).

---

## What the owner is asked to approve or do

1. Approve this plan, or change it.
2. Owner work:
   - for A: check about 40 hard-query labels;
   - for B1: fill 60 more blind shortlists;
   - later: decide on log storage for B3.
3. Render settings, when the gates pass: `LLM_PARSER=on`, `RAG_EXPLAIN=on` and the key, set by the owner.
