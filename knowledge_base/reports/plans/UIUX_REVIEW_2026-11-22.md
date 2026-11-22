# CarRec: independent UI/UX review

Reviewed 22 Nov 2026 against the **live site** (https://carrec.onrender.com, already awake, no cold start seen). Front-end code was read, not edited, in `/Users/shaikyaseenbasha/carrec_worktrees/app-rag` (branch `fix/rag-followups`). The live `script.js` contains the same functions, including `buildWhyRag`, but the live API returned no `explanation_rag` for any query I ran, so the cited AI explanation was **not** visible live. Its code was reviewed only.

Method: a single-context review. The impeccable `critique` flow asks for two isolated sub-agents; I did not spawn any (see §5). I used the built-in browser pane at 1280×800 (desktop), the pane's own 800 px width, and the 375×812 mobile preset, in light and dark. I also used DOM measurements via JS and headless Chrome for a few extra captures. File and line references are to the worktree.

Queries exercised:
1. `automatic SUV under 15 lakh with sunroof` (standard)
2. `family ke liye 7 seater diesel, Mahindra nahi chahiye` (Hinglish, through the follow-up box)
3. `7 seater diesel, no Mahindra` (exclusion)
4. `electric 7 seater convertible under 5 lakh with manual gearbox` (restrictive)
5. `7 seater automatic diesel under 6 lakh with sunroof and ADAS` (very restrictive)
6. `good car`, `sasti gaadi`, `asdfgh qwerty` (vague / garbage)
7. `Ferrari under 10 lakh` (brand not covered)
8. `sedan with sunroof`, then a chip search, then Back (navigation)

---

## 1. Verdict and scores

CarRec has a clear, honest idea with mostly good craft. The landing page states the task in one sentence, the search box is the only thing to do, and Hinglish works. The results are unusually transparent: what we understood, "Not met / Not verified" pills, dated sources, and caveats from owners. The tokens, contrast and focus styles are better than most products at this stage. The problems are about density and trust in the results.

- **Cards are too long.** Each card is 600–790 px on desktop and 1,320–1,580 px on a phone, so a user sees one car per screen.
- **The three score bars confuse more than they help.** They use one visual for three different scales. A 4.4/5 owner rating is drawn as a nearly empty bar.
- **The main button leaves the site.** The most prominent action on every card is "Check on-road price", which opens CarDekho.
- **Several inputs are dropped silently.** "Ferrari", "convertible" and "no Mahindra" never show in what we understood.
- **"Top pick" contradicts the card.** It still crowns a car that meets 2 of 6 requirements.
- **Detail view is a 6,000 px panel.** Most of it is an 83-row table, and picking a variant gives no feedback.
- **No compare, sort or filter.** For a shortlist tool, that is the biggest functional gap.

| Area | Score /10 | One-line reason |
|---|---|---|
| First impression | **8** | Strong hero, plain promise, Hinglish chips show the differentiator immediately. |
| Clarity of the core task | **7** | One input, one button. Undermined by silent ignores and 3–10 s waits behind a generic spinner. |
| Result-card design | **5** | Honest and well-sourced, but overlong, with confusing meters, a misplaced primary CTA and no way to compare. |
| Detail page | **5** | Complete specs, but buried under an 83-row table. Variant switching is silent and not shareable. |
| Mobile | **6** | No broken layout except one overflow. Cards are ~2 screens tall and the on-road CTA sits ~1,400 px down. |
| Accessibility | **7** | Good contrast, real buttons, visible focus, `aria-expanded`, sensible headings. Hurt by a whole-thread live region, rotating chips and lost focus. |
| Visual polish | **7** | Coherent token system, nice dark mode, calm palette. Internal jargon and a mismatched header on /project spoil it. |

---

## 2. What works and should be kept

- **The hero.** The headline "Tell us what you need. We'll find the right car." over a dimmed brochure mosaic is specific and warm. The single search plus example chips is the right model. Keep the copy.
- **Hinglish chips** ("sunroof wali SUV 12 lakh ke andar", "family ke liye 7 seater diesel"). They are the clearest proof of what makes the product different.
- **"What we understood" echo chips**, including *assumed* chips with a Remove button (`script.js:407-420`). This is the right pattern for a free-text parser, so extend it (see C3).
- **Honest labelling.** "Meets 2 of 6 requirements" with "Not met: petrol, not diesel" and "Not verified: ADAS" pills, the "Nothing matched every requirement" notice, "a few owners" qualifiers and dated sources. Trust is the product, and this delivers it.
- **Caveats block** (owner negatives in a warn panel). Rare and valuable.
- **Tokens and contrast.** All text pairs measured pass AA (table in C17). The focus ring is 3 px at 5.3:1 (light) and 9.0:1 (dark). Dark mode is fully tokenised.
- **Mechanics.** Back/forward restores the right turn and search text. Shared `/?q=` links work. `prefers-reduced-motion` is respected for the mosaic, the spinner and chip rotation. Touch targets are at least 24 px (none smaller found). Card photos have alt text.
- **Relaxation transparency** ("Showing the closest, with budget up 20% (to ₹6 lakh) and any fuel type").

---

## 3. Change list (ranked by impact ÷ effort)

| ID | Area | Problem and evidence | Exact change | Impact | Effort | Type |
|---|---|---|---|---|---|---|
| C1 | Results toolbar (all widths) | Internal pipeline id shown to shoppers: "Car data updated 22 Nov 2026 · knowledge base kbpipe-ev_range_windsor_brochure_2026-11-22-review" (every query, desktop and mobile). Wrapped in `.nowrap`, it overflows at 375 px: span right edge 387 px vs 359 px wrap, page `scrollWidth` 387 > 375, so the page scrolls sideways. `script.js:244`. | Remove the `kb_phase` span from `buildDataStamp`. Copy: **"Prices and specs updated 22 Nov 2026"**. If the id is needed for debugging, put it in a `title` attribute or behind `?debug=1`. | High | S | bug / copy |
| C2 | Result card, top badge | "Top pick" goes to index 0 whatever the fit. Query 5 crowns a Maruti Celerio that "Meets 2 of 6 requirements", has "Not met: 5 seats, 7+ asked", and is "among the lowest-rated hatchbacks". `script.js:672`. | Show "Top pick" only when `violations.length === 0 && not_verified.length === 0`. Otherwise label rank 1 **"Closest match"** with the same pill style but `--surface-2` background and `--ink-2` text. | High | S | usability / copy |
| C3 | "What we understood" | Exclusions and ignored words disappear. "Mahindra nahi chahiye" and "no Mahindra" are applied (no Mahindra in results; API `exclude_makes:["Mahindra"]`) but never echoed: `understoodChips` has no `exclude_makes` (`script.js:376-404`). "convertible" (query 4) and "Ferrari" (query 7) are silently dropped. `unsupported_terms` is `[]`, so no banner appears and 8 unrelated cars show. | (a) Add `(it.exclude_makes \|\| []).forEach(x => need("No " + x))`, and the same for `exclude_features`. (b) Show an "ignored" chip for any query token the parser didn't use: outline `1px dashed var(--line-strong)`, text `--ink-3`, label **"Didn't use: convertible"**. (c) For an unknown or uncovered brand, show the existing `.notice` with **"We don't cover Ferrari. Showing cars under ₹10 lakh instead."** This needs the API to return the term. | High | M | usability / bug |
| C4 | Card score meters | Three identical bars mean three different things. "Specs · fit to your search" is a 0–100 fit; Expert and Owners are percentile standings within the body type. A 4.4/5 owner rating (Nissan Gravite) renders as a bar of **5** with "among the lowest-rated MPVs". Kia Syros 9/10 → 93, Nexon 8/10 → 58. A car labelled "Meets all your requirements" shows Specs **81**, and users will ask where the other 19 went. The explanatory footnote is 13 px `--ink-3` below the bars. `script.js:330, 465-488`, `style.css:554-564`. | Replace the three bars with one compact row of labelled values, no bars: **"Reviewers: 8/10 (Autocar, above average for SUVs) · Owners: 4.6/5 from 1,068 (above average)"**. Lead with the raw rating and keep the standing as words. Drop the Specs number from the card entirely, since the match label already covers fit. If a visual is wanted, use a 5-dot standing scale (well below → well above) instead of 0–100 bars. | High | M | usability |
| C5 | Card actions | The primary filled button on every card is "Check on-road price ↗", an external CarDekho link (`script.js:702`, `.btn-primary`). The in-app "View details" is the quiet secondary. So the most prominent action takes users off the site before they compare. | Swap emphasis: "View details" becomes `.btn-primary`. On-road price becomes a text link with the external icon, 15 px, `--accent-text`, underlined, labelled **"On-road price on CarDekho ↗"**, placed under the ex-showroom price in `.car-price`, where price questions arise. | High | S | usability |
| C6 | Card length | Measured card heights: desktop 1280 px, 601–792 px (8 cards = 6,937 px page); mobile 375 px, 1,318–1,579 px (8 cards = 13,117 px). This contradicts the design note "card stays <= 340px tall" (`style.css:375-377`). Breakdown on mobile: meters 188, fit block 282, caveats 163, two review columns 141+141, footer 158 px. | Make the collapsed card a summary: photo, name, variant, price, facts row, match label and pills, up to 2 "why" bullets, the chips row, actions. Move "What reviewers say", "What owners say" and "Caveats" behind the existing toggle, renamed **"Reviews and owner feedback (3)"**. Keep one caveat line visible when present, as a 1-line warn pill, e.g. "⚠ Some owners report fit-and-finish issues". Targets: ≤ 380 px desktop, ≤ 720 px mobile. On mobile keep the photo at 21:9 but cap its height at 140 px. | High | M | visual / usability |
| C7 | Compare | No compare anywhere (searched DOM text, templates and JS). Shortlisting 2–3 cars is the natural next step after a ranked list. | Add a "Compare" checkbox-button to each card footer (`aria-pressed`, 40 px). With 2–4 selected, show a sticky bottom tray: 64 px, `--surface`, top border `--line`, thumbnails + **"Compare 3 cars"** primary. Clicking opens `/compare?ids=…`, a table of price, gearbox, fuel, mileage/range, seats, boot, NCAP, airbags, ADAS, sunroof, reviewer and owner rating. Highlight the best value per row in `--good`. Sticky first column on mobile. | High | L | usability |
| C8 | Inline details panel | "View details" inserts a panel **6,013 px tall** (Nexon). The 83-row variant table is 4,256 px, with all 61 non-matching variants listed. The specs for the chosen variant start ~4,500 px below the button. The `th { position: sticky }` never sticks because `.table-wrap` has `overflow-x:auto` (`style.css:467-470`). | Show only matching variants by default (22 here), capped at 8 rows, with **"Show all 83 variants"** below. Give `.table-wrap` `max-height: 420px; overflow: auto` so the sticky header works. Move "Specifications" above "Variants" so the selected variant's specs come first. In the inline panel, show only Summary + Key specs + a **"Full details →"** link to `/car/<make>/<model>?q=…` instead of the whole page. | High | M | usability |
| C9 | Variant selection (detail page and panel) | Clicking a variant row gives **no visual feedback for 4–8 s**: `loadDetail` only shows the spinner when the body is empty (`script.js:835`). Then the whole panel re-renders, keyboard focus drops to `<body>` (measured), the URL doesn't gain `variant_id`, and the changed specs sit ~3,000 px below the click point. | On click: mark the row `aria-busy` and show a 16 px spinner in its first cell immediately. Fetch, then replace only the Specifications/Safety/Warranty sections, not the table. Restore focus to the clicked `.variant-pick`. `history.replaceState` with `?variant_id=`. Show a toast/`role="status"` line: **"Showing specs for Creative Plus (S) AMT Dark Edition ↓"** with a jump link. | High | M | bug / accessibility |
| C10 | Search loading | Measured `/predict` latency: 3.0–4.1 s for structured queries, **10.3–10.6 s** for vague ones ("good car", "sasti gaadi"). The only feedback is "Finding cars that match…" in a 200 px box (`script.js:991`). | Show the parsed chips first if the parser is fast (or echo the query chips client-side). Replace the box with 3 skeleton cards: 200 px tall, `--surface-2` shimmer, static under reduced motion. Step the copy over time: 0 s "Reading your request…", 2 s "Checking 1,556 variants…", 6 s "Ranking by reviews and owner feedback…". | Med | S | usability |
| C11 | Screen-reader announcement | The whole results thread is `aria-live="polite"` (`recommend.html:23`), as is the car-detail article (`car.html:14`). Each render injects ~5–8k words, which some screen readers will read in full and others drop. After a search, focus stays in the input. | Remove `aria-live` from `#results` and `#car-detail`. Add one `<p class="sr-only" role="status" id="search-status">` that receives **"8 cars found for 7 seater diesel, no Mahindra. Nothing matched every requirement."** For turns after the first, move focus to the new `.turn-head` (it already has `tabindex="-1"`). | Med | S | accessibility |
| C12 | Very restrictive queries | For query 5 the engine relaxed seats 7→5 and fuel→any and returned 4 small hatchbacks. The message is a 4-sentence run-on. The user can't choose *which* requirement to give up: `relaxation_hints` were empty, so the hint buttons in `buildRelaxationHints` (`script.js:218`) never appear. | Under the notice, render the relaxations as removable choices: **"We relaxed: [Seats 7+ → 5+ ✕ undo] [Diesel → any fuel ✕ undo]"** plus "Or drop instead: [Sunroof] [ADAS] [Budget]" buttons that re-run with `drop=`. Shorten the notice to the first sentence plus "We relaxed seats and fuel to show the closest cars." | Med | M | usability / copy |
| C13 | Car detail page | Unknown model `/car/tata/nonexistent` (HTTP 404) shows "Something went wrong. We couldn't load the details for this car. Please try again." Retrying cannot help. The `<title>` is "Car details" until JS loads. Headings jump H1 → H3 (`renderDetail`). The page omits "Why this car", reviews and caveats, so it has less than the card it came from. | 404 copy: **"We don't have that car"** / "It may be discontinued or the link is wrong." + "Search cars" button. Render the `<title>` server-side. Make section titles `h2` (`.detail-section h3` → `h2`, same styles). Add the reviewers/owners/caveats blocks under Summary when `q` is present. | Med | S | bug / accessibility / copy |
| C14 | Car names | The car name `h3.car-title` is plain text (`script.js:679`). Users can't open a car in a new tab or share it except via the "Copy link" inside the expanded panel. | Wrap the title in `<a href="/car/<make>/<model>?q=…">` with `text-decoration: none`, underline on hover/focus. Keep "View details" for the inline expand. | Med | S | usability |
| C15 | Suggestion chips | Chips re-shuffle every 8 s (`script.js:1110-1113`, `SUGGESTION_ROTATE_MS`). They pause on hover and focus, but a touch user reading a chip can have it change under the thumb. This also counts as auto-updating content without a stop control (WCAG 2.2.2). | Stop auto-rotation and keep "More ideas ↻" as the manual refresh. If rotation is kept for the hero only, stop it permanently after the first user interaction (scroll, touch or keydown). | Med | S | accessibility |
| C16 | Sort and filter | There is no way to re-order 8 results (price, mileage, safety) or narrow them, other than re-typing the query. | Add a 40 px toolbar row above the cards: **Sort: Best match ▾ / Price ↑ / Mileage / Safety rating**, as a native `<select>` on mobile. Client-side sort of the current recs only. Mark the active choice in the URL (`&sort=price`). | Med | M | usability |
| C17 | Non-text contrast | Text contrast passes everywhere: light `--ink-3` on bg 5.35, on surface-2 4.90; warn 6.29; accent-soft 6.64; good 5.55; white on accent button 5.67; dark `--ink-3` 6.38–7.03; dark button 7.58. But control borders are `--line-strong` `#cbc5b8` on `#f7f5f0` = **1.58:1** (chips, "Copy link", "View details"), and dark `#44474e` on `#1b1d21` = **1.81:1**. Photo captions `#f3f1ec` over the 62% gradient can fall to **~3.2:1** at 12 px on bright photos. | Darken `--line-strong` to `#8f897c` (light, ≈3.1:1 on bg) and `#6a6d75` (dark, ≈3.2:1) for interactive borders only. Keep `--line` for dividers. Captions: raise the gradient end to `rgb(14 15 18 / 0.78)` and the font to 13 px. | Med | S | accessibility |
| C18 | Duplicate content in card | Tata Punch EV shows the same owner theme twice, in "What owners say" and in "Caveats" (the "Service experience · Negative · 4 of 31 reviews" text appears twice, query 1). | When building the card, skip in `buildOwnerBlock` any note whose `theme+label` is already in `car.caveats`, and fall back to the next owner note or the ratings summary. | Low | S | bug |
| C19 | Mobile search box | At 375 px the placeholder truncates to "e.g. safe family SUV under 15 lakh w…", and the first chip truncates to "SUV with ADAS and 360 camera under 25…" (mobile landing screenshot). | Shorter mobile placeholder via JS/`matchMedia` or a shorter universal one: **"e.g. family SUV under 15 lakh"**. Use a `textarea` that auto-grows to 2 lines on < 560 px, so long Hinglish queries stay visible while typing. Cap chip text at about 28 characters in `suggested_queries.json` for chips shown on mobile. | Low | S | usability |
| C20 | Vague query result | "good car" returns a "Please note" notice plus 8 "General pick, not personalised" cards, each still showing "Specs · fit to your search" bars, which mean nothing here. The recovery is a sentence, not an action. | When `vague` is true, replace the notice body with 4 tappable refiners: **[Under ₹10 lakh] [Family / 7 seats] [City / automatic] [Best mileage]**. Each appends to the query and re-runs. Hide the Specs meter on non-personalised cards. | Low | S | usability |
| C21 | /project header and numbers | /project uses a different header ("Back to CarRec · Overview · Pipeline · Knowledge base · Engine · Theme: Auto") from the app. Its first paragraph says "1,619 variants" while the homepage says "We check 1,556 current variants". It leads with "29.4% of stored values … recorded no source", internal-audit language one click from the main nav. | Use the shared `_header.html` with a sub-nav. Reconcile counts with one wording, e.g. "1,619 variants stored, 1,556 currently on sale". Move audit metrics below a plain-language intro, or move the page out of primary nav into the footer ("How CarRec works (technical)"). | Low | M | copy / visual |
| C22 | Theme | /project has a light/dark/auto toggle; the main app follows the OS only. | Add the same toggle to `_header.html`, storing it in `localStorage` (try/catch) and setting `data-theme` on `<html>`. Or remove it from /project for consistency. | Low | S | visual |

---

## 4. Quick wins (under an hour each)

1. **C1** Remove the KB phase id from the data stamp. This also fixes the 375 px horizontal scroll.
2. **C2** "Top pick" only when all requirements are met; otherwise "Closest match".
3. **C3a** Echo `exclude_makes` / `exclude_features` as "No Mahindra" chips (a 2-line change in `understoodChips`).
4. **C5** Swap button emphasis: "View details" primary, CarDekho as a text link by the price.
5. **C10** Staged loading copy plus skeleton cards.
6. **C11** Replace the whole-thread `aria-live` with one status sentence, and focus the new turn heading.
7. **C13** 404 copy, server-side `<title>`, `h3`→`h2` on the detail page.
8. **C14** Make car names links to `/car/...`.
9. **C15** Turn off chip auto-rotation.
10. **C17** Darken interactive borders and strengthen the caption gradient.
11. **C18** De-duplicate owner notes that also appear in Caveats.
12. **C19** Shorter mobile placeholder.

---

## 5. Not tested, and why

- **The cited AI explanation ("Why this car" with numbered sources, `buildWhyRag`).** It is present in live JS, but no live query returned `explanation_rag`, so I could only review the code. One note from the code: the sources list stays hidden until "Show more from reviews", and clicking a citation expands the card, which then jumps the layout.
- **Cold start.** The site was already awake on first load, so I could not observe the up-to-60 s Render wake-up or how the page behaves during it. Given C10, a cold start probably leaves the spinner up with no explanation. Worth checking.
- **Mobile screenshots below the fold.** The browser pane's mobile emulation returned blank or cropped images after scrolling. Headless Chrome enforces a ~500 px minimum window width, so its "375 px" captures render wider and are **not** used as evidence. Mobile findings below the fold rest on DOM measurements taken at the emulated 375×812 viewport (card heights, section heights, overflow, touch-target sizes), not on images.
- **Real screen readers** (VoiceOver/NVDA) were not run. The C11 claims come from the markup.
- **Copy link / clipboard.** I did not click it, to avoid writing to the user's clipboard.
- **Used cars** (`/used`). It is behind a feature flag and not in the live nav, so it was not reviewed.
- **Comparisons.** None exist in the product (C7).
- **Review method.** The impeccable critique protocol asks for two isolated sub-agents (design review plus detector). This review was done in one context, without spawning agents. The bundled detector ran on `templates/` but could not resolve the Jinja stylesheet link. Its single finding ("flat type hierarchy, h1 = body = 16px") is a **false positive** caused by that, so it was discarded.
