> DEGRADED: single-context. I ran the design review and the detector/browser pass in one context, not as two isolated sub-agents. I am already a sub-agent, and the brief asked for one independent reviewer. The impeccable detector ran on `templates/`, but it could not resolve the Jinja `url_for` stylesheet links, so its colour, type and padding findings are mostly false positives. I did not use them. Everything below comes from the live site and from reading the code.

# CarRec: independent UI/UX review (cold read)

- **Site tested:** live, https://carrec.onrender.com, on 2026-11-23. It was already awake; I did not run the app locally.
- **Code read (read-only):** `scratchpad/main_before/templates/*.html`, `static/style.css`, `static/script.js`. There is no PRODUCT.md or DESIGN.md.
- **Viewports:**
  - "Desktop": the browser pane's native size, about 800×600 CSS px. A 1280×800 emulation rendered blank screenshots after any scroll, so I worked at the native size.
  - Mobile: the 375×812 preset (Android UA, DPR 2). Emulated screenshots also went blank after a scroll, so to capture lower parts of the page I shifted `<main>` up with a CSS transform (inspection only) instead of scrolling.
  - Light and dark colour schemes.
- **Queries run:**
  1. `automatic SUV under 15 lakh with sunroof` (Q1, normal)
  2. `7 seater diesel gaadi chahiye 20 lakh tak, Mahindra nahi` (Q2, Hinglish)
  3. `electric 7 seater under 8 lakh with ADAS` (Q3, very restrictive)
  4. `good car` (Q4, vague)
  5. `diesel automatic sedan under 12 lakh` (Q5, no exact match)
  6. `Ferrari convertible under 5 lakh` (Q6, unsupported brand)
  7. `sunroof wali SUV 12 lakh ke andar` (timing only)

---

## 1. Verdict and scores

CarRec is better than most portfolio-grade recommenders. The core promise ("type what you want, get honest matches") is delivered. The parser visibly shows what it understood. The system is candid about what it relaxed and what it could not verify. The visual system is restrained and coherent, in both light and dark mode.

The weak points are elsewhere:
- **Density and disclosure on the result card.** One card carries about 20 pieces of information, three different expanders and a full-strength primary button.
- **Continuity between the steps of the flow.** Back re-runs the search and loses your place. The car page can open on a different variant than the card you tapped. The compare tray follows you into unrelated searches.
- **Mobile.** On a phone, no result is visible above the fold, each car takes a whole screen, and the 4-car comparison shows 1.3 cars at a time.

None of these need a redesign. They are mostly layout, state and copy fixes.

| Area | Score /10 | Why |
|---|---|---|
| First impression | 8 | Clear promise, real brochure-photo mosaic, the search is the hero, Hinglish chips signal the differentiator at once. |
| Clarity of the core task | 8 | One box and one button. The "What we understood" echo and the relaxation panel are excellent. Lost points: no visible result count, and results sit below the fold. |
| Result-card design | 6 | Honest, well-sourced content, but too much of it at equal weight. Disclosure is mislabelled, and price placement shifts between cards. |
| Detail page | 6 | Solid spec sheet and a good summary paragraph. But it can open on a variant that contradicts the card, reviews appear only sometimes, it has no compare action, and its variant table is a nested scroll box. |
| Mobile | 5 | Nothing is broken (no horizontal page scroll), but it is inefficient: results start about 740 px down, each card is about 740 px tall, the textarea clips the query on load, and compare is cramped. |
| Accessibility | 7 | Strong base: tokenised colours that pass AA (numbers below), visible 3 px focus ring, live status line, `aria-pressed`/`aria-expanded`, table caption, reduced-motion handling. Missing: a skip link, a visible result count, a heading jump on the detail page, plus one clipped input. |
| Visual polish | 7 | Calm paper-and-ink palette, one accent, consistent radii. It is let down by pill overload: five pill styles on one card, some clickable and some not. |

---

## 2. What works and must be kept

- **"What we understood" echo chips**, with assumptions and corrections styled differently and "Didn't use: convertible" for ignored words (Q6). This is the product's best trust feature.
- **The relaxation panel** (Q3, Q5): "No car matches everything you asked for. We relaxed: budget up 10% (to ₹8.8 lakh)…" plus one-tap "Without fuel type · 5 models". This is honest and actionable.
- **Per-card match label** ("Meets 3 of 4 requirements" with "Not met: … / Not verified: …"), and "General pick, not personalised" on the vague query, which also offers refiners (Under ₹10 lakh, Family / 7 seats, City / automatic, Best mileage).
- **Unsupported-brand handling** (Q6): "We don't cover Ferrari. Showing cars under ₹5L instead."
- **Hinglish works end to end** (Q2): it understood Under ₹20L, Diesel, 7+ seats and No Mahindra.
- **Source attribution everywhere**: "Image: Tata brochure", "Autocar India · … · Jul 2025", "9 of 60 reviews, CarWale". Keep it.
- **The compare tray, and the compare table with sticky row labels and "Best" pills.** Selection persists through the trip to `/compare` and back.
- **Loading copy** ("Reading your request…" → "Checking 1,556 variants…" → "Ranking by reviews…") with skeletons. It makes a 3.5–10 s wait tolerable.
- **The colour tokens**, which pass AA numerically. These are my own calculations from the `:root` values in `style.css` lines 33–53 and 66–90:

  | Pair | Light | Dark |
  |---|---|---|
  | `--ink-3` on `--bg` | 5.35:1 | 7.03:1 |
  | `--ink-3` on `--surface-2` | 4.90:1 | n/a |
  | warn text on warn-soft | 6.29:1 | n/a |
  | white on accent button | 5.67:1 | n/a |
  | accent text on accent-soft | 6.64:1 | n/a |
  | control borders (`--line-ctl`) | 3.19–3.48:1 | 3.26–3.59:1 |
  | accent-ink on accent | n/a | 7.58:1 |

  Do not trade these away in any restyle.
- **No auto-rotating chips** (WCAG 2.2.2 respected), `prefers-reduced-motion` honoured on the hero drift and on smooth scrolls.

---

## 3. The change list

These are ranked by impact on users divided by effort. Evidence uses: **D** = desktop pane (about 800×600), **M** = 375×812 mobile, and the query IDs Q1–Q7 from the list above.

| ID | Area | Problem, with evidence | The exact change | Impact | Effort | Type |
|---|---|---|---|---|---|---|
| 1 | Results: search box on load | **The query is clipped on page load.** The textarea shows one and a half lines of a two-line query ("…20 / lakh tak, Mahindra nahi" cut mid-glyph). M, Q2. Cause: `initNewCarPage` sets `userQuery.value = first.q` (`script.js` ~l.1731), but `fitSearchBox` already ran in `initSearchBoxes` on DOMContentLoaded, before the value existed. The same happens on popstate (~l.1718). | Call `fitSearchBox(document.getElementById("userQuery"))` right after every programmatic `.value =` assignment: initial load, popstate and suggestion pick. | High | S | bug |
| 2 | Results: count and position | **No visible result count, and results start below the fold.** "8 cars found…" lives only in the `sr-only` `#search-status`. The first card's top is at y≈490 on D and y≈740 on M (Q1, Q2), so on a phone the user submits and sees only the search box, chips and query echo. | (a) Add a visible line in the turn header under the query: "8 cars · sorted by best match", at `--text-sm`, `--ink-2`. Keep the sr-only status as it is. (b) On the first search, when `matchMedia('(max-width: 767px)')` matches, scroll the turn heading to just under the sticky header once results render (`scrollToTurn` already exists; today it runs only for later turns, `runSearch` ~l.1507). (c) On results pages at ≤767px, hide the top suggestion chips once a turn exists; the follow-up form already offers chips. | High | S | usability |
| 3 | Back/forward | **Back from compare or a car page re-runs the whole search and loses your place.** After Back from `/compare`: skeleton plus "Checking 1,556 variants…" for about 3.5 s (Q1; measured `/predict` 3.5 s, and 9.6 s for Q4), then `scrollY = 0`, expanded panels closed and suggestion chips reshuffled. Cause: `history.scrollRestoration = "manual"` (l.1661) plus no response cache. | Cache each `/predict` response in `sessionStorage` keyed by `q + drop` (TTL 30 min). On a load whose navigation type is `back_forward`, render from cache with no skeleton. Before leaving the page (`pagehide`), save `{scrollY, expandedCardIds, openReviewIds}` in `history.replaceState`, and restore them after render. Keep the suggestion set stable for the turn by seeding the shuffle from the query. | High | M | usability |
| 4 | Card → car page continuity | **The car page can open on a different variant than the card you tapped.** Q5's Kia Sonet card shows "HTK Plus Diesel 1.5L Turbo Automatic (TC) ₹11.45 lakh", but the title link `/car/kia/sonet?q=…` opens on "HTE Petrol 1.2L 5 Speed Manual · ₹7.45 lakh". `linkCarTitles` (l.1488) passes make, model, q and drop only. Q1's Nexon happened to line up. | Add the card's variant to the link: `&variant=<id>` (the id is already on the Compare button as `data-compare`). Make `/api/car` honour it as `selected_variant_id`. Use the same id for the "Full details →" button inside the inline panel. | High | S | bug |
| 5 | Result card: disclosure | **Key reasons are hidden behind the wrong toggle.** Q1's Nexon card shows 2 "why" reasons. Clicking "Reviews and owner feedback (7)" also reveals 2 more reasons ("Priced at ₹14.02 lakh, 93% of your ₹15 lakh budget" and an owner rating). The budget-fit reason is the most relevant one for the query, and it sits behind a reviews button. `buildV3Card`: reasons with index ≥ `V3_REASONS_SHOWN` get `data-more hidden`, and `toggleReviews` un-hides every `[data-more]`. | Always show the budget-fit reason first when the query has a budget, and show up to 3 reasons. Never put reasons under the reviews toggle: give `toggleReviews` its own selector (`[data-reviews-more]`). If more than 3 reasons exist, add an inline text button "+2 more reasons" under the list. | High | S | usability |
| 6 | Result card: hierarchy and density | **Too much at equal weight.** Each card stacks name, variant, price, ex-showroom, on-road link, "also available from", a 3-fact row, a match label, a reviewers+owners line, 2–4 reasons, a caveat pill, 2–4 tag pills, a variant-count pill and 3 buttons, all at 13–15 px (D, Q1). On M one card is about 740 px tall (Q2), about one card per screen. Redundant pieces: the "Sunroof" pill repeats "Has sunroof, as you asked"; "Meets all your requirements" repeats on all 8 cards when every card meets everything; "22 matching variants" has no action attached. | (a) When every card in a turn is a full match, show "All 8 meet every requirement" once in the turn header, and drop the per-card label (keep it when cards differ). (b) Remove feature pills that repeat a reason. (c) Make "N matching variants" a link to `/car/…#detail-variants`, or drop it. (d) Merge the reviewer and owner line into one compact row: "★ 8/10 Autocar · 4.6/5 owners (1,068)". (e) At ≤599px, cap the photo at `aspect-ratio: 16/9; max-height: 180px`. Target card height on M: ≤560 px. | High | M | visual |
| 7 | Result card: actions | **Eight solid accent "View details" buttons on one page** compete with "Find cars" and "Compare 2 cars". There are also three expansion models: View details (inline panel), Full details → (page), and Reviews (inline). | Restyle "View details" as `btn-quiet`, and keep one filled accent button per viewport (the search button, or the compare tray when it is open). Rename the inline toggle to "Specs & variants". Rename "Reviews and owner feedback (7)" to "Reviews (7)". On ≤599px, put the three actions in one row: 2 buttons at 1fr each, with Reviews as a full-width text-style toggle below at 44 px tall. | Med | S | visual |
| 8 | Pills: affordance | **Clickable and non-clickable pills look the same.** Non-interactive pills: the echo chips (Under ₹15L, SUV…), "We relaxed: any body type", feature and safety tags, the caveat pill. Interactive pills: the suggestion chips and "Without fuel type · 5 models". All are rounded, bordered pills (D, Q5 screenshot). | Make non-interactive chips borderless with a `--surface-2` fill and `border-radius: 6px`, so they read as labels. Keep a full pill with a border only for buttons, and give buttons a hover state plus a leading icon (↻, ✕, +). Inside the relaxation panel, render "We relaxed: budget up 10% (to ₹8.8 lakh), any fuel type" as plain inline text, not pills. | Med | S | usability |
| 9 | Compare tray | **The selection leaks into unrelated searches.** The Nexon + XUV 3XO picked in Q1 stayed in the tray during Q3, Q4 and Q5 ("2 cars selected") and covered about 70 px at the bottom of M. Comment at l.812: "survives new searches". | Keep persistence, but collapse the tray to a 44 px pill, "Compare (2)", bottom-right, whenever none of the selected cars is in the current turn. Expand it on tap. Add `padding-bottom` to `main` equal to the tray height while it is open, so the last card's buttons are never covered. | Med | S | usability |
| 10 | Compare page: mobile | **The 4-car comparison is hard to use on a phone.** At M, 1.3 columns are visible, with no cue that more columns exist (`.compare-scroll` scrollWidth 712 vs clientWidth 341). The row-label column takes about 115 px. Car names scroll out of view vertically, so lower rows lose their column identity. | At ≤599px: make the label column 96px with labels at 13 px; make car columns `min-width: 44vw` so 2 fit; add a right-edge fade mask plus a "1–2 of 4 →" indicator above the table. Make the `thead` row sticky (`top: 64px`) with a compact header: 48 px thumbnail, model name only, no variant line. Add a "Show differences only" toggle that hides rows where every cell is equal. | Med | M | usability |
| 11 | Copy: inconsistent unknowns | The same missing value has three labels: the card says "Mileage: Not listed" (Sonet, Venue, Q1/Q5); compare says "Not verified" for the same car; mileage shows as "24.1 kmpl" on the card and "24.08 kmpl" in compare and on the detail page. | Use one label everywhere: "Not confirmed". Use one precision rule: 1 decimal for kmpl and km/kg in every view. | Med | S | copy |
| 12 | Copy: lowercase/raw tokens | "Not met: suv, not sedan" (Q5, D). | Map body types to display labels in the not-met strings: "Not met: SUV, not a sedan". Check the other raw enums (fuel, gearbox) through the same mapper. | Med | S | copy |
| 13 | Detail page: matching variants | "22 of 83 variants match your search", but only 8 rows show; the other 14 matches sit behind "Show all 83 variants" (Nexon, Q1, D; DOM: 22 rows tagged `is-match`, 8 visible). "Matches your search" also repeats as a badge on every row. | Show all matching rows by default. Change the button to "Show the other 61 variants". Replace the per-row badge with the existing row tint plus one legend line above the table: "Tinted rows match your search". | Med | S | usability |
| 14 | Detail page: scroll trap | The variants table is a 420 px-tall box that scrolls on both axes inside a page that scrolls (M: 663 px content in a 307 px box, `max-height: 420px; overflow-y: auto`). On a phone the inner box captures the swipe. | Remove `max-height` and `overflow-y`. Keep horizontal scroll only. At ≤599px, render each variant as a stacked row (name on line 1; price · gearbox · fuel · mileage on line 2), so no horizontal scroll is needed. | Med | M | usability |
| 15 | Detail page: reviews appear only sometimes | The Nexon page opened from a search shows "What reviewers and owners say". The Kia Sonet page shows no reviews section, whether opened from Q5 or directly, even though its card offers "Reviews and owner feedback (7)". `buildReviewsSection` only renders when the payload carries reviews from the search. | Return reviews from `/api/car` itself, independent of `q`, so every car page (including shared links) shows them. Order: Summary → Reviews → Specs. | Med | M | bug |
| 16 | Detail page: navigation | The Nexon page runs about 5 screens on D and Sonet's Variants heading is at y≈2840 on M. There is no in-page navigation, no Compare action, and the price range wraps "ex-" / "showroom" onto two lines on M. | Add a sticky sub-nav under the header: "Summary · Reviews · Specs · Safety · Variants" (horizontal scroll on M, 40 px tall, active section underlined). Add "Add to compare" (same tray logic) next to "Copy link". Use `white-space: nowrap` on the "ex-showroom" span. | Med | M | usability |
| 17 | Car page shell on mobile | The whole page is wrapped in a bordered, padded card inside `.wrap`, which costs about 40 px of width on a 375 px screen (photo 307 px wide). The loading state is a card inside a card. | At ≤599px, remove the outer card's border, radius and padding (`.detail-body--page`), letting sections run to the 16 px gutter. Replace the loading box with a skeleton of the real layout (photo block, title line, two spec rows). | Low | S | visual |
| 18 | Keyboard | No skip link. A keyboard user tabs through 5 header controls, the textarea, Find cars and 6 suggestion chips (13 stops on Q5) before the first result. | Add `<a class="skip" href="#results">Skip to results</a>` as the first focusable element, visible on focus (top-left, `--surface`, 3 px focus ring). On the car page, target `#car-detail`. | Med | S | accessibility |
| 19 | Result card layout | Price position varies between cards: right-aligned for XUV 3XO, Venue and Syros, but stacked under the title for Nexon, because the long variant name forces `.car-head` to wrap (D, Q1). | Fix the grid: `.car-head { display: grid; grid-template-columns: 1fr auto; }` with the variant line spanning under the title, so the price always sits top-right on desktop. Clamp the variant name to 2 lines with a `title` attribute. | Low | S | visual |
| 20 | Compare button accessible name | The name is read as "Compare Compare Tata Nexon Fearless Plus…" (visible label plus sr-only text; seen in the tab-order capture). | Use `aria-label="Add Tata Nexon Fearless Plus … to compare"` on the button (and "Remove … from compare" when pressed), and drop the sr-only span. | Low | S | accessibility |
| 21 | Header | "How it works" on `/recommend` navigates to `/#how-it-works`, leaving the results. On M the theme button reads only "Auto", which is not self-explanatory. | Hide "How it works" from the nav on results and car pages (keep it on the homepage). On M, show a sun/moon/auto icon with `aria-label="Theme: Auto"` and a `title`, at a 44×44 tap area. | Low | S | usability |
| 22 | Empty submit | Submitting an empty box does nothing on both the landing page (`onsubmit` returns false) and results (`runSearch` returns), with no feedback. | On an empty submit, focus the textarea and show a helper below it for 3 s: "Type what you need, e.g. 'family SUV under 15 lakh'" (`role="status"`). | Low | S | usability |
| 23 | Hero mosaic loading | On first paint the mosaic shows empty dark tiles with visible seams before the images arrive (D, 1280 emulation, first load). | Fade each `img` in on `load` (`opacity 0 → 1`, 300 ms, skipped under reduced motion), and use the same colour for the tile background and `--hero-bg`, so unloaded tiles read as one dark field. | Low | S | visual |
| 24 | Data shown to users | Some displayed values contradict each other. Exter "HX 10 Petrol Automatic ₹9.42 lakh — Also available from ₹6.91 lakh (HX 10 Petrol Automatic Dual Tone)", a dual-tone version of the same trim priced lower (Q1). For Q4 ("good car"), the third pick is a ₹30.15 lakh XEV 9S among ₹7–19 lakh cars. | Not a UI fix: flag these to the data owner. UI guard: when "also available from" names the same trim as the headline variant, hide that line. | Low | S | bug |

---

## 4. Quick wins (under an hour each)

- **#1**: re-fit the textarea after a programmatic value set (one line in 3 places).
- **#2a**: a visible "8 cars · sorted by best match" line.
- **#2b**: scroll to results on the first mobile search (the function already exists).
- **#4**: pass `variant=<id>` in the card's title link.
- **#5**: stop hiding reasons under the reviews toggle; budget-fit reason first.
- **#7**: "View details" to `btn-quiet`; shorter button labels.
- **#8**: restyle non-interactive chips as flat labels.
- **#11 and #12**: unify "Not confirmed", 1-decimal mileage, display labels for "suv".
- **#13**: show all matching variant rows by default.
- **#16** (partly): `nowrap` on "ex-showroom".
- **#18**: skip link.
- **#19**: grid on `.car-head`.
- **#20**: the Compare `aria-label`.
- **#21**: hide "How it works" on the results page.
- **#22**: empty-submit helper.
- **#23**: hero image fade-in.

---

## 5. Not tested, and why

- **Real iOS Safari and Android devices.** Only Chromium emulation was available. The 375×812 emulation produced blank screenshots after any scroll, so for below-the-fold mobile screens I used a CSS transform on `<main>` (inspection only) or DOM measurements. Sticky-header behaviour during real scroll on mobile is therefore unverified.
- **A true 1280px+ desktop layout.** The pane is about 800 px wide, and a 1280×800 emulation rendered blank after scrolling. The wide two-column card and the 4-column compare at 1280+ were seen only on first paint or not at all.
- **Screen-reader output.** No VoiceOver or NVDA was available. I checked the accessible tree, names, roles, the live status line and tab order only.
- **The `/project` pages and the used-cars flow.** I did not review `/project` in depth. `/used` is a "coming soon" page; `used.html` (Tailwind, a different visual language) is not served live.
- **Cold-start behaviour on Render.** The site was already awake. Measured `/predict` latency in-browser: 3.5 s (Q1), 3.6 s (Q7), 9.6 s (Q4).
- **Copy link** (clipboard permission) and the CarDekho and Autocar outbound links. Not clicked through.
- **The impeccable detector's live-page overlay** was not injected. The CLI scan of `templates/` could not resolve the Jinja stylesheet, so its output was not usable as evidence.
