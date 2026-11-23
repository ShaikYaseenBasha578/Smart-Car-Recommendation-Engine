# Plan: the five open follow-ups, 23 Nov 2026 (awaiting owner approval)

The owner asked for all five in one go:
- the parser misreadings;
- slow vague searches;
- the Back-button cache (PR I) and car page improvements (PR J);
- the /project overflow on phones;
- the stale UI gates.

This plan covers them as six pull requests. Everything below was checked on `main` at 5def662 before planning.

## Ground rules (as before)

- **Who does what:** Sonnet builds and Opus reviews. The impeccable skill is used for any UI change, and every visible change has before/after screenshots at desktop 1280 and mobile 375, light and dark.
- **PRs:** each PR is cut from the latest `main` and the owner merges; there is no stacking.
- **Tests:** run only from a worktree's `tests/`.
- **Eval:** unless a PR says otherwise, the eval stays byte-identical:
  - main: 193/193 zero-violation, 182 verified;
  - held-out: 105/107, 91 verified.
- **KB:** the production KB is only read, through a hash-checked copy, and only for regenerating /project pages.

## What was found

| Item | Finding on main |
|---|---|
| "nothing above 13 lakh" | Read as a **minimum** of ₹13L (`budget.min = 1300000`). |
| "car under 4 metres" | Read as a **₹4L budget** ("under 4"). |
| "car that can tow a trailer" | The typo corrector turns "trailer" into **Triber** and adds it as a model. |
| "sunroof bilkul nahi" | **Requires** a sunroof. "nahi chahiye" works; "bilkul nahi" isn't treated as a negation. |
| "I can't drive a manual" | Sets the gearbox to **manual**. |
| "fast charging EV" | "fast" adds the **performance** soft preference. |
| "nexon or punch" | Keeps only the **Nexon**. |
| "AMT nahi" | Excludes AMT correctly, but **also sets the family to automatic**, so manuals are dropped. |
| "high ground clearance" | Not used. It shows the PR D "Didn't use: ground clearance" chip, so it is honest today. |
| "EV with 450 km range" | **Already parsed correctly** (minimum range 450 km). Dropped from the list. |
| Slow vague search | Locally "good car" takes 0.66 s against 0.35 s for "SUV under 15 lakh"; on Render about 10 s against 3–4 s. The profile shows `compute_criteria` 0.47 s, `diversify` 0.19 s and `blank_prior` 0.13 s, mostly pandas `iterrows`, per-row `Series` building and element-wise `__setitem__`. A vague query scores every variant, so these loops dominate. Much of the per-variant work does not depend on the query. |
| /project overflow | **Engine page:** the "limits" list items are 367 px wide at 320 and 360 px. **Knowledge-base page:** 332 px at 320 (the culprit is not found by a quick scan; the build finds it). Overview and pipeline are fine. Both pages come from the page generator (`kbpipe/dashboard.py`). |
| Stale UI gates | `tests/ui_gates.py` on main: **43 pass, 10 fail**, then it crashes at the details-panel step, so the mobile checks never run. The failures are checks written for designs that PRs A–C replaced: "every card ≤ 340 px", the old panel headings, "data stamp + external price in panel", match-label wording, reason-wording checks and the EV "Range" check. The script also only finds Chromium at Playwright's default path. |

## The pull requests, in order

### 1. Gates: bring `tests/ui_gates.py` up to date (small)
- Rewrite each failing check to the design as it now is, and say in the PR what each was and what it is now:
  - card-height limits become the measured PR H values with a margin (desktop at most 460, mobile median at most 640);
  - the panel shows Summary, Key specs and "Full details →";
  - the "Matches your search" rows;
  - the current label wording;
  - the EV range fact;
  - reason checks against the current reason set.
- Remove nothing silently: a check that no longer has a meaning is listed as removed, with the reason.
- The Chromium path comes from an environment variable (`CARREC_CHROMIUM`), falling back to Playwright's default, so it runs here without a wrapper.
- **Done when:** the whole file runs to the end on main at desktop and mobile, light and dark, with 0 failures, and the PR E compare gate is included.
- Why it goes first: the later PRs can then use the full gate set.

### 2. /project overflow on phones (small)
- Fix the two causes in the generator's CSS (`kbpipe/dashboard.py` on kb/kbpipe): the engine "limits" list, and whatever makes the KB page 332 px wide.
- Regenerate the four pages from a read-only, hash-checked copy of the KB, as in PR F, and sync them into the app.
- **Done when:**
  - no /project page scrolls sideways at 320, 360, 375 and 1280;
  - the text diff of the regenerated pages shows only the generated date and figures that changed since 23 Nov.

### 3. Faster vague searches (medium; touches scoring code, **results must not change**)
- Precompute the query-independent parts of the criteria once per catalogue load: per-variant values, blank priors and segment populations.
- Replace the row-by-row pandas loops in `criteria.py`, `score.py` and `diversify.py` with vectorised operations.
- No weights, formulas, thresholds or tie-breaks change.
- **Exception to the UI rule:** this PR may edit `score.py`, `criteria.py` and `diversify.py`, because that is where the time goes. The proof that nothing changed is stricter than for UI PRs:
  - the full ranked output (every card's variant, order, scores to 6 decimals, reasons and labels) for all 369 main and held-out queries is byte-identical to main;
  - the eval files are byte-identical.
- **Done when:**
  - "good car" takes at most 0.35 s locally (from 0.66), and every query is no slower;
  - after the owner merges, Render's "good car" time is measured (median of 5) and reported against the 9.6 s the reviewer saw.
  - If 0.35 s is not reachable without changing results, report the best achieved.

### 4. Parser fixes (medium; **changes parses on purpose**)
Each case below gets a rule fix in `services/intent_v2.py` (and `services/typos.py` for "trailer"). Each fix is pinned by a test with the expected parse:

| Query | Today | After |
|---|---|---|
| nothing above 13 lakh / kuch bhi 13 lakh se upar nahi | min ₹13L | max ₹13L |
| car under 4 metres / sub 4 metre | budget max ₹4L | no budget; "Didn't use: size" (see decision 1) |
| car that can tow a trailer | model Triber | no model ("trailer" is a word, not a typo) |
| sunroof bilkul nahi / sunroof bilkul nahi chahiye | sunroof required | sunroof excluded |
| I can't drive a manual / can't do manual | manual | automatic |
| fast charging EV | performance preference | electric; "Didn't use: fast charging" |
| nexon or punch (under 10 lakh) | Nexon only | Nexon and Punch |
| AMT nahi | automatic, not AMT | not AMT (manual still allowed) |

**The typo fix:** a common English word ("trailer", and others) is never corrected into a model or make name. It is checked against a small built-in list of words seen in queries, plus a rule that a correction needs a much closer match when the word is a plain word.

**Gates (the parses change, so these replace "byte-identical"):**
- Every parse change across the 369 eval queries is listed in the PR, before and after.
  - Only queries containing one of the patterns above may change.
  - Any other change is a bug and is fixed before the PR opens.
- Zero-violation counts do not drop (main 193/193, held-out 105/107), and the verified counts do not drop.
- The 40 hard queries are scored before and after. They are still drafts that the owner hasn't ticked, so the result is reported, not used as a gate.
- If more than 20 eval parses change, a fresh blind Opus agent judges a stratified sample of before/after parse pairs against the query text, without seeing the code. The bar is at least 95% agreement in each class.
- The "Didn't use" chip lexicon (PR D) is unchanged; "size" and "fast charging" are already in it.

### 5. PR I: Back keeps your results (medium)
- Each `/predict` answer is cached in `sessionStorage`, keyed by query, drops and the catalogue's export date, so a data update never shows stale results. It lives 30 minutes, and every storage call is guarded.
- On Back or forward, results come from the cache with no skeleton and no `/predict` call.
- Scroll position, open detail panels, expanded reviews, the expanded reasons and the sort are saved in `history.state` before leaving, and restored.
- The suggestion chips stay the same set for that search.
- **Done when:** a Playwright gate shows search → car page → Back (and search → compare → Back) renders with **no** `/predict` request, lands within 50 px of where you were, and keeps an opened panel open. The full gate set passes.

### 6. PR J: car page improvements (medium)
- **All matching variants shown:** with a search, every matching row shows; the button reads "Show the other 61 variants". One legend line, "Tinted rows match your search", replaces the per-row badge.
- **Reviews on every car page:** `/api/car` returns the model's reviewer, owner and caveat notes itself, read-only from the same stored review data the cards use. So a shared link or a direct visit shows them, not only a visit from a search.
- **A section menu** under the header: Summary · Reviews · Specs · Safety · Variants. It is sticky, scrolls sideways on phones, and underlines the active section.
- **"Add to compare"** on the car page, using the same tray and selection as the results page.
- **Done when:** the gates pass, a direct `/car/kia/sonet` visit shows reviews, and the Nexon search page shows all 22 matching rows.

## Order and parallel work

The owner asked for one go. PRs 1, 2 and 3 touch separate files:
- PR 1: `tests/ui_gates.py`;
- PR 2: the generator and `project_pages/`;
- PR 3: the scoring internals.

So they can be **built at the same time**, each in its own worktree from `main`, and opened as three separate PRs. They are not stacked, and any order of merging works.

PRs 4, 5 and 6 then follow **one at a time**, each from `main` after the previous merge:
- PR 4 changes what the eval measures;
- PRs 5 and 6 share `script.js` and the car page.

## Decisions for the owner (defaults used if you just approve)

1. **"under 4 metres":** stop the budget misreading and show "Didn't use: size" (default). The alternative is to also add a real hard length filter (`max_length_mm`). That is a new requirement type: blank lengths would pass as "not verified", as other filters do.
2. **"high ground clearance" (no number):** keep it as an honest "Didn't use" chip (default). The alternative is a new soft preference that favours taller clearance in ranking.
3. **Scoring files in PR 3:** allow PR 3 to edit `score.py`, `criteria.py` and `diversify.py` under the byte-identical proof above (default yes). If not, PR 3 is dropped.
4. **Parallel build:** build PRs 1–3 at the same time (default), or strictly one after another.
5. **Gate limits in PR 1:** desktop card at most 460 px, mobile median at most 640 px (default, the PR H result plus a margin), or tighter.

## Cost and size

- All the work is local: no paid API calls.
- PR 4 may need one blind agent.
- The owner merges six PRs. The PR 3 Render timing is measured after its merge.
