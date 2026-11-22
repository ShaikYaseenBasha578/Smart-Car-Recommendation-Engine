# Plan: UI follow-up after the 23 Nov re-review (awaiting owner approval)

**Source:** the blind re-review of the live site, `UIUX_REVIEW_2026-11-23.md` in this folder. Its change ids (#1–#24) are used below. Mobile dropped from 6 to 5; the other areas held or rose.

Claude checked these claims against `main` (6e1090f) before planning:
- **#1 is a bug.** `initNewCarPage` sets the search text after `initSearchBoxes` has already sized the box, so a two-line query is clipped on load and on Back.
- **#4 is a bug.** `linkCarTitles` builds the car link from make, model, q and drop only, with no `variant_id`. The car page already accepts `variant_id` (PR C).
- **#5 holds.** `toggleReviews` un-hides every `[data-more]` element, and that includes the "why" reasons beyond the first 2.
- **#12 holds.** "suv, not sedan" is written by `services/recsys/relax.py:263` from the raw body-type value.
- **#11 holds.** The card says "Not listed" (`buildFacts`), while the car page and compare say "Not verified".

## Ground rules (same as the UI plan)

- **Who does what:** Sonnet builds, and Opus designs and reviews, using the impeccable skill.
- **Branches:** one PR at a time, each from the latest `main`; no stacking. Claude never merges.
- **Screenshots:** desktop 1280 and mobile 375, light and dark, before and after.
- **No change to what is recommended:**
  - the eval stays byte-identical: main 193/193 with 182 verified, held-out 105/107 with 91 verified;
  - no edits to `score.py`, `config.py`, `criteria.py`, `diversify.py`, `relax.py`, `llm_parse.py` or `ml_parser/`.
- **Tests:** the full `tests/` suite passes, new behaviour gets tests, and the compare gate stays green.

## PR G: the two bugs and correctness fixes (small, about half a day)

| Id | Change |
|---|---|
| #1 | Re-fit the search box after every time the code sets its text: first load, Back/forward, and a suggestion pick (`fitSearchBox` already exists). |
| #4 | The card title link and the panel's "Full details →" carry `variant_id` (the card's own variant), so the car page opens on the variant the card showed. A test checks the link for a card whose variant is not the model's cheapest. |
| #5 | Reasons no longer sit behind the reviews toggle:<ul><li>the reviews toggle gets its own selector;</li><li>the budget-fit reason, when the query has a budget, is always among the 2 shown;</li><li>any further reasons go behind an inline "+N more reasons" text button.</li></ul> |
| #12 | "Not met" lines show display words: "SUV, not a sedan", "Diesel, not petrol". This is done in `script.js` by mapping the known raw values (body type, fuel, gearbox family) at the start of the line, because `relax.py` is off-limits in UI PRs. |
| #11 | One word for an unknown value: the card's "Not listed" becomes "Not verified", as on the car page and compare. Mileage shows 1 decimal in every view (card, compare and car page). |
| #20 | The Compare button's accessible name is read once ("Add Tata Nexon Fearless Plus to compare"), not "Compare Compare …". |
| #18 | A "Skip to results" link is the first focusable element (on the car page it reads "Skip to details"). |

## PR H: mobile density (about 1–2 days)

**Target, measured in the PR:** the median collapsed mobile card at most 560 px tall (it is about 720–740 today), and the first card's top within the first screen after a search at 375 × 812.

| Id | Change |
|---|---|
| #2 | <ul><li>A visible line under the query: "8 cars · sorted by best match" (it follows the sort).</li><li>On phones, the first search also scrolls to its results.</li><li>Once results exist, the top suggestion chips are hidden on phones; the follow-up box already has its own.</li></ul> |
| #6 | <ul><li>When every card in a search meets every requirement, "All 8 meet every requirement" is shown once above the cards, and the per-card label is dropped. It stays per card when the cards differ.</li><li>Feature pills that repeat a reason are removed.</li><li>"N matching variants" becomes a link to the car page's variants section.</li><li>The reviewer and owner line becomes one compact row.</li></ul> |
| #7 | <ul><li>"View details" becomes a quiet outline button; the filled accent stays for "Find cars" and the compare tray.</li><li>"View details" is renamed "Specs & variants", and "Reviews and owner feedback (7)" becomes "Reviews (7)".</li><li>On phones the actions sit in one row.</li></ul> |
| #9 | The compare tray collapses to a small "Compare (2)" pill when none of the selected cars is in the current results, and opens on tap. |
| #10 | The compare page on phones:<ul><li>2 car columns per screen, with a "1–2 of 4 →" cue;</li><li>a sticky compact header row (thumbnail and model);</li><li>a "Show differences only" toggle.</li></ul> |
| #14 | The car page's variants table no longer scrolls inside the page on phones. Each variant becomes a stacked row (name; then price · gearbox · fuel · mileage). This reverses PR C's 420 px scroll box on phones only; desktop keeps it. |
| #17 | On phones the car page drops its outer card border and padding, so content uses the full width. |

## Not in these two PRs (listed so nothing is lost)

- **#3, Back re-runs the search:** a session cache of results, and restoring scroll position and open panels. This is medium-sized, with its own risks (stale results after a data update), so it goes in its own PR I if wanted.
- **#13, #15, #16 (the car page):**
  - show all matching variants;
  - load reviews on every car page, not only when it is opened from a search (PR C's known gap);
  - an in-page sub-nav and an "Add to compare" button.

  Possible PR J.
- **#8, #19, #21, #22, #23:** small polish (flat label chips, price alignment, header link on results, empty-submit hint, hero fade-in). These can join PR H if it stays small, or come later.
- **#24 is data, not UI:**
  - The Exter "HX 10 … Dual Tone" priced below the same trim is the known edition-base problem (editions 815/816, held under P8; it is owner item N4 in CLAUDE.md). It is not fixed in the UI. Optionally, PR G can hide "Also available from" when it names the same trim.
  - The ₹30 lakh XEV 9S ranking third for "good car" is a scoring question for vague queries, and belongs with the vague-query latency work.

## Decisions for the owner (defaults used if you just approve)

1. **#12 wording:** map the raw values in the browser (default), or allow a display-only change to the `relax.py` strings in PR G. That change would not alter results; the eval would confirm it.
2. **#11 word for unknowns:** keep "Not verified" everywhere (default), or switch every view to the reviewer's "Not confirmed".
3. **#5 reasons shown:** keep 2 plus "+N more" (default, which protects the card height), or show 3 as the reviewer suggests.
4. **#14 variants table on phones:** stacked rows (default), or keep the scroll box.
5. **Order:** PR G first, then PR H (default). PR I (Back cache) and PR J (car page) are only planned if you ask.

## Owner decision

- 23 Nov: plan approved with the five default decisions. PR G started.
