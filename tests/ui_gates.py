"""Browser gates for the UI (not collected by pytest; needs Playwright + Chromium).

    python tests/ui_gates.py http://127.0.0.1:5201 [--shots DIR]

Runs every user flow at 1440x900, 1366x860 and 375x812, each in light and dark colour scheme (6 runs), and prints one
PASS/FAIL line per check. Exit status 1 if any check fails. Prints a PASS/FAIL count per run at the end.

How to run (any free port; the server must not use the LLM parser or the RAG explainer, so unset them):

    cd <worktree> && env -u RAG_EXPLAIN -u LLM_PARSER python -c "import app; app.app.run(port=5201)"
    python tests/ui_gates.py http://127.0.0.1:5201

CARREC_CHROMIUM=<path to a chromium / chrome-headless-shell executable> overrides Playwright's own browser.
Restart the server after a template change.

Updated for the design after PR C (inline panel + car page), E (compare), G (budget reason), H (phone card, count line).
Old check -> new check (checks not listed are unchanged):
  desktop "match labels" (Great/Good/Fair match)  -> "All N meet every requirement" once above the cards, or per-card
                                                    "Meets k of n requirements" / "Closest match" (the Great/Good/Fair badge is gone)
  every card <= 340px (desktop only)              -> desktop every card <= 460px; mobile median <= 640px and every card <= 760px
  [ev] 'Range: <n> km' on every card              -> desktop 'Range: <n> km' or 'Range: Not verified'; phone (labels hidden) '<n> km' or
                                                    'Not verified'; plus a range is shown wherever the response has one
  [cng] card <= 340px                             -> covered by the new card-height limits
  laptop ">= 2 full cards after scrolling the first to the top"
                                                  -> same rule, but the first card is placed just under the header (scrollIntoView stops 168px
                                                    down because of the card's scroll-margin plus the page's scroll-padding)
  "More ideas rotates chips" in the top box       -> on phones the top box hides its chips once a thread exists (PR H), so the follow-up box's
                                                    More ideas is used there
  [sunroof] no reason mentions SUV or sunroof     -> REMOVED: the design now says "Has sunroof, as you asked" on purpose (PR H);
                                                    replaced by "the sunroof is shown once, as a reason or a tag" (already present)
  [sunroof] budget reasons are headroom           -> with a budget, a budget reason ("Priced at Rs X lakh, N% of your budget") is among the
                                                    shown reasons of every card (PR G); the old "Rs N L under your budget" wording is gone
  [sunroof] no bare 'Fits your budget'            -> kept (still true)
  [sunroof] 'N airbags' only when highest; no standout label on 3+ cards; 'Lowest price here' within Rs 10k
                                                  -> REMOVED: these tested buyerReasons(), the legacy v1 card; v3 cards show the server's
                                                    reasons, so the checks passed with nothing to test. Replaced by "no reason repeated within a
                                                    card" (PR H de-duplication)
  [detail] panel shows all 5 section headings     -> inline panel has Summary + Key specs + 'Full details ->' link (PR C); the car page has
                                                    Summary, Specifications, Safety, Warranty, Variants (reviews section optional)
  [detail] data stamp + external on-road price in panel
                                                  -> data stamp in the panel; the external on-road link now lives on the card and the car page
  [detail] >= 1 'Matches your search' row         -> same check on the car page opened from the search
  [detail] variant click changes specs (in panel) -> same check on the car page (variants are not in the panel any more)
  [detail] phone variants                         -> NEW: stacked rows (not table rows), no inner vertical scroll (PR H)
  [cng] panel table never shows kmpl for CNG      -> same rule on the car page's variants table
  [slavia] panel lists DCT variants as matches    -> same rule on the car page reached through the panel's 'Full details' link
  "5 star safety sedan" shows a .tag--unverified chip -> an unverified requirement now reads "Confirmed on k of n requirements" with a
                                                    "Not verified: ..." line; the .tag--unverified chip is checked on the relaxed search
  "CVT automatic hatchback" gives an empty state + hints -> the catalogue now has a match, and a no-match search shows relaxed closest cars
                                                    instead of an empty state: query "CVT automatic hatchback under 5 lakh" -> notice, drop hints,
                                                    "Closest match" badge, per-card "Meets k of n requirements", "Not met:" lines, "N closest cars"
  mobile run never reached (crash on .spec-groups in panel) -> fixed, the run now goes to the end
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from playwright.sync_api import sync_playwright

VIEWPORTS = {"desktop": (1440, 900), "laptop": (1366, 860), "mobile": (375, 812)}
SCHEMES = ("light", "dark")
CHROMIUM = os.environ.get("CARREC_CHROMIUM") or None
# card height limits (owner-approved 23 Nov): desktop every card; phone median and every card
MAX_CARD_HEIGHT_DESKTOP = 460
MAX_CARD_HEIGHT_MOBILE_MEDIAN = 640
MAX_CARD_HEIGHT_MOBILE = 760
CARD_QUERIES = {"sunroof": "sunroof wali SUV 12 lakh ke andar", "cng": "CNG gaadi under 8 lakh", "ev": "EV under 15 lakh"}
BUDGET_REASON = re.compile(r"Priced at ₹[\d.,]+ (lakh|crore), \d+% of your ₹[\d.,]+ (lakh|crore) budget|Right at your budget|₹[\d.]+L under your budget", re.I)
BANNED = ["ML Intent", "Latency", "Regex", "Execute", "/new_cars", "Ranking logic", "confidence"]
MAX_HOME_BYTES = 3 * 1024 * 1024

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  -- ' + str(detail)) if detail else ''}", flush=True)


# visible text containing a banned string, outside #how-it-works
BANNED_JS = """(banned) => {
  const hits = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode, el = node.parentElement;
    if (!el || el.closest('#how-it-works, script, style')) continue;
    if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) continue;
    for (const b of banned) if (node.textContent.toLowerCase().includes(b.toLowerCase())) hits.push(b + ': ' + node.textContent.trim().slice(0, 60));
  }
  for (const el of document.querySelectorAll('[placeholder], [title], [aria-label], img[alt]')) {
    if (el.closest('#how-it-works')) continue;
    const t = ['placeholder', 'title', 'aria-label', 'alt'].map(a => el.getAttribute(a) || '').join(' ');
    for (const b of banned) if (t.toLowerCase().includes(b.toLowerCase())) hits.push(b + ' (attr): ' + t.slice(0, 60));
  }
  return hits;
}"""

MONO_JS = """() => {
  const bad = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode, el = node.parentElement;
    if (!el || !node.textContent.trim() || el.closest('code, pre, kbd, samp, script, style')) continue;
    if (!el.checkVisibility()) continue;
    const ff = getComputedStyle(el).fontFamily.toLowerCase();
    if (/mono|courier|consolas|menlo/.test(ff)) bad.add(el.tagName + ': ' + ff);
  }
  for (const el of document.querySelectorAll('input, button')) {
    const ff = getComputedStyle(el).fontFamily.toLowerCase();
    if (/mono|courier|consolas|menlo/.test(ff)) bad.add(el.tagName + ': ' + ff);
  }
  return [...bad];
}"""


def page_checks(page, label):
    hits = page.evaluate(BANNED_JS, BANNED)
    check(f"{label}: no banned strings outside #how-it-works", not hits, hits[:3])
    mono = page.evaluate(MONO_JS)
    check(f"{label}: no monospace", not mono, mono[:3])
    sw, vw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    check(f"{label}: no horizontal overflow", sw <= vw, f"{sw} > {vw}" if sw > vw else "")


def predict(page, action):
    """Run action and wait for the /predict response plus the render that follows it."""
    with page.expect_response(lambda r: r.url.endswith("/predict"), timeout=60_000) as resp:
        action()
    response = resp.value
    page.wait_for_function("!document.querySelector('[data-turn-body] .loading')", timeout=15_000)
    return response


def full_shot(page, path):
    """Scroll through the page first so lazy card photos load, then capture it whole."""
    page.evaluate("""async () => {
        for (let y = 0; y < document.body.scrollHeight; y += innerHeight / 2) { scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); }
    }""")
    page.wait_for_load_state("networkidle")
    page.evaluate("scrollTo(0, 0)")
    page.screenshot(path=path, full_page=True)


CARD_INFO_JS = """() => [...document.querySelectorAll('article.car')].map(c => {
    const r = c.getBoundingClientRect(), photo = c.querySelector('.car-photo').getBoundingClientRect(),
          body = c.querySelector('.car-body').getBoundingClientRect();
    return {
        name: c.getAttribute('aria-label'), height: Math.round(r.height),
        photoAbove: photo.bottom <= body.top + 1, photoLeft: photo.right <= body.left + 1,
        facts: c.querySelector('.facts').innerText.replace(/\\s+/g, ' '),
        reasons: [...c.querySelectorAll('.reasons li')].map(li => li.textContent.trim()),
        shown: [...c.querySelectorAll('.reasons li:not([hidden])')].map(li => li.innerText.trim()),
        fit: (c.querySelector('.fit-label') || {}).innerText || '',
        rank: (c.querySelector('.rank') || {}).innerText || '',
        chips: [...c.querySelectorAll('.tag')].map(t => t.innerText.trim()),
    };
})"""


def card_checks(page, base, tag, w, shots):
    for key, q in CARD_QUERIES.items():
        predict(page, lambda: page.goto(base + "/recommend?q=" + quote(q)))
        cards = page.evaluate(CARD_INFO_JS)
        check(f"{tag} [{key}]: has cards", cards, len(cards))
        heights = [c["height"] for c in cards]
        if w >= 1024:
            check(f"{tag} [{key}]: every card <= {MAX_CARD_HEIGHT_DESKTOP}px tall", all(h <= MAX_CARD_HEIGHT_DESKTOP for h in heights), heights)
            check(f"{tag} [{key}]: photo left of content", all(c["photoLeft"] for c in cards))
        else:
            median = sorted(heights)[len(heights) // 2]
            check(f"{tag} [{key}]: median card <= {MAX_CARD_HEIGHT_MOBILE_MEDIAN}px, every card <= {MAX_CARD_HEIGHT_MOBILE}px",
                  median <= MAX_CARD_HEIGHT_MOBILE_MEDIAN and max(heights) <= MAX_CARD_HEIGHT_MOBILE, f"median {median}, max {max(heights)}")
            check(f"{tag} [{key}]: photo above content", all(c["photoAbove"] for c in cards))
        sw, vw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        check(f"{tag} [{key}]: no horizontal overflow", sw <= vw, f"{sw} > {vw}" if sw > vw else "")
        dupes = [(c["name"], r, ch) for c in cards for r in c["reasons"] for ch in c["chips"]
                 if r.lower() in ch.lower() or ch.lower() in r.lower()]
        check(f"{tag} [{key}]: no reason duplicates a chip", not dupes, dupes[:3])
        repeated = [c["name"] for c in cards if len({r.lower() for r in c["reasons"]}) != len(c["reasons"])]
        check(f"{tag} [{key}]: no reason repeated within a card", not repeated, repeated[:3])
        if w == 1366:
            # put the first card just under the sticky header (scrollIntoView adds the card's scroll-margin and the page's
            # scroll-padding, 168px in all, which is not where a reader stops)
            page.evaluate("""() => {
                const top = document.querySelector('.site-header').getBoundingClientRect().bottom;
                scrollTo({ top: scrollY + document.querySelector('article.car').getBoundingClientRect().top - top - 8, behavior: 'instant' });
            }""")
            page.wait_for_timeout(300)
            full = page.evaluate("""() => {
                const top = document.querySelector('.site-header').getBoundingClientRect().bottom;
                return [...document.querySelectorAll('article.car')].filter(c => {
                    const r = c.getBoundingClientRect(); return r.top >= top - 1 && r.bottom <= innerHeight + 1;
                }).length;
            }""")
            check(f"{tag} [{key}]: >= 2 full cards visible with the first just under the header", full >= 2, full)
        if key == "cng":
            kmkg = [c for c in cards if "km/kg" in c["facts"]]
            check(f"{tag} [cng]: a card shows km/kg", kmkg, len(kmkg))
            # cards whose response has mileage_km_per_kg must never say Not verified
            data = page.evaluate("q => fetch('/predict', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query: q})}).then(r => r.json())", q)
            have = {f"{r['Make']} {r['Model']}" for r in data["recommendations"] if r.get("mileage_km_per_kg")}
            bad = [c["name"] for c in cards if c["name"] in have and ("Not verified" in c["facts"] or "km/kg" not in c["facts"])]
            check(f"{tag} [cng]: km/kg shown wherever it exists", have and not bad, bad or f"{len(have)} with km/kg")
        if key == "ev":
            # desktop prints "Range: 465 km"; on phones the facts line has no visible labels (PR H), so only the value is checked.
            # An unknown range reads "Not verified", never blank or 0.
            pattern = r"Range: (\d+ km|Not verified)" if w >= 1024 else r"(\d+ km|Not verified)$"
            bad = [c["facts"] for c in cards if not re.search(pattern, c["facts"])]
            check(f"{tag} [ev]: every card shows its range ('Range: <n> km') or 'Not verified'", not bad, bad[:2])
            data = page.evaluate("q => fetch('/predict', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query: q})}).then(r => r.json())", q)
            have = {f"{r['Make']} {r['Model']}" for r in data["recommendations"] if r.get("ev_range_km")}
            bad = [c["name"] for c in cards if c["name"] in have and not re.search(r"\d+ km", c["facts"])]
            check(f"{tag} [ev]: range shown wherever it exists", have and not bad, bad or f"{len(have)} with a range")
        if key == "sunroof":
            # PR H: the sunroof is asked for, so the card says so ("Has sunroof, as you asked"); no check that reasons avoid it
            nobudget = [c["name"] for c in cards if not any(BUDGET_REASON.fullmatch(r) for r in c["shown"])]
            check(f"{tag} [sunroof]: a budget reason is among the shown reasons of every card (PR G)", not nobudget, nobudget[:3])
            budget = [r for c in cards for r in c["shown"] if "budget" in r.lower()]
            check(f"{tag} [sunroof]: budget reasons read as headroom or '% of your budget'", budget and all(BUDGET_REASON.fullmatch(r) for r in budget), budget[:3])
            check(f"{tag} [sunroof]: no bare 'Fits your budget'", not any("fits your" in r.lower() for c in cards for r in c["reasons"]))
            print(f"INFO  {tag} [sunroof] reasons: " + " | ".join(f"{c['name']}: {c['reasons']}" for c in cards))
        if shots and w in (1366, 375):
            full_shot(page, f"{shots}/{tag.replace("/", "-")}-{key}.png")


PANEL_HEADINGS = ["Summary", "Key specs"]                                   # the inline panel (PR C)
PAGE_HEADINGS = ["Summary", "Specifications", "Safety", "Warranty", "Variants"]  # the car page; a reviews section may sit after Summary
REVIEWS_HEADING = "What reviewers and owners say"


def open_panel(page, card_index=0):
    """Expand a card's detail panel and wait for its content."""
    card = page.locator("article.car").nth(card_index)
    with page.expect_response(lambda r: "/api/car/" in r.url, timeout=30_000):
        card.locator("[data-detail]").click()
    panel = page.locator(".cards > .detail.open").first
    panel.locator(".detail-section h3").first.wait_for()
    page.wait_for_timeout(450)  # expand transition
    return panel


def car_page(page, url, tag, w, errors=None):
    """Open a /car/<make>/<model> page and wait for its sections."""
    resp = page.goto(url)
    page.locator("#car-detail .detail-section > h2").first.wait_for(timeout=30_000)
    return resp


def variants_checks(perm, tag, w):
    """Variants table on the car page: stacked rows with no inner vertical scroll on phones."""
    wrap = perm.locator("#variants-table")
    if w < 640:
        info = perm.evaluate("""() => {
            const wrap = document.querySelector('#variants-table'), tr = wrap.querySelector('tbody tr:not([hidden])');
            return { rowDisplay: getComputedStyle(tr).display, wrapOverflowY: getComputedStyle(wrap).overflowY,
                     scrolls: wrap.scrollHeight > wrap.clientHeight + 1, maxHeight: getComputedStyle(wrap).maxHeight };
        }""")
        check(f"{tag} [variants]: stacked rows (not table rows), no inner vertical scroll on phones",
              info["rowDisplay"] != "table-row" and not info["scrolls"] and info["maxHeight"] == "none", info)
    else:
        check(f"{tag} [variants]: table keeps its own bounded scroll on desktop", wrap.count() == 1)


def detail_checks(page, base, tag, w, shots):
    # sunroof: reason rules, the inline panel and the car page behind it
    q = CARD_QUERIES["sunroof"]
    predict(page, lambda: page.goto(base + "/recommend?q=" + quote(q)))

    panel = open_panel(page, 0)
    headings = panel.locator(".detail-section h3").all_inner_texts()
    check(f"{tag} [detail]: inline panel has Summary and Key specs", headings == PANEL_HEADINGS, headings)
    check(f"{tag} [detail]: panel sits directly under its card",
          page.evaluate("() => document.querySelector('.cards > .detail').previousElementSibling.matches('article.car')"))
    check(f"{tag} [detail]: panel has key specs and no variants table",
          panel.locator(".spec-list dt").count() >= 3 and panel.locator("table.variants").count() == 0, panel.locator(".spec-list dt").count())
    check(f"{tag} [detail]: data stamp in the panel", panel.locator(".data-stamp").count() == 1)
    full = panel.locator("a.detail-full")
    href = full.get_attribute("href") if full.count() == 1 else None
    check(f"{tag} [detail]: 'Full details ->' link carries the search", href and full.inner_text().startswith("Full details")
          and href.startswith("/car/") and "q=" in href, href)
    sw, vw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    check(f"{tag} [detail]: no horizontal page overflow with a panel open", sw <= vw, f"{sw} > {vw}" if sw > vw else "")
    panel_btn = page.locator("article.car").first.locator("[data-detail]")
    panel_btn.click()
    page.wait_for_timeout(450)
    check(f"{tag} [detail]: panel collapses", page.locator(".cards > .detail").count() == 0 and panel_btn.inner_text() == "Specs & variants")

    # the car page, opened from that search through the panel's link
    errors = []
    perm = page.context.new_page()
    perm.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    perm.on("pageerror", lambda e: errors.append(str(e)))
    resp = car_page(perm, base + href, tag, w)
    heads = perm.locator("#car-detail .detail-section > h2").all_inner_texts()
    core = [h for h in heads if h != REVIEWS_HEADING]
    check(f"{tag} [detail]: car page has every section", resp.status == 200 and core == PAGE_HEADINGS, heads)
    matches = perm.locator("tr.is-match", has_text="matches your search").count()   # the per-row badge is now a screen-reader-only text (PR J)
    check(f"{tag} [detail]: >= 1 matching row on the car page", matches >= 1, matches)
    check(f"{tag} [detail]: car page has the data stamp and the external on-road price link",
          perm.locator(".data-stamp").count() == 1 and perm.locator(".detail-actions a[target=_blank]").count() == 1)
    variants_checks(perm, tag, w)
    # picking another variant redraws the specs
    before = perm.locator(".spec-groups").inner_text()
    selected = perm.locator("tr.is-selected").get_attribute("data-variant-id")
    rows = perm.locator("tbody tr:not([hidden])")
    target = None
    sel_gear = perm.locator("tr.is-selected td").nth(2).inner_text()
    for i in range(rows.count()):  # prefer a variant with a different gearbox, so specs must change
        if rows.nth(i).get_attribute("data-variant-id") != selected and rows.nth(i).locator("td").nth(2).inner_text() != sel_gear:
            target = rows.nth(i); break
    target = target or rows.nth(1 if rows.nth(0).get_attribute("data-variant-id") == selected else 0)
    target_name = target.locator(".variant-pick").inner_text()
    with perm.expect_response(lambda r: "/api/car/" in r.url and "variant_id=" in r.url):
        target.click()
    perm.wait_for_function("name => document.querySelector('#pick-status').innerText.includes(name)", arg=target_name)
    after = perm.locator(".spec-groups").inner_text()
    check(f"{tag} [detail]: clicking a variant row changes the spec values", before != after and
          perm.locator("tr.is-selected .variant-pick").inner_text() == target_name, target_name)
    sw, vw = perm.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    check(f"{tag} [detail]: car page has no horizontal overflow", sw <= vw, f"{sw} > {vw}" if sw > vw else "")
    perm.close()

    # CNG: no kmpl presented as CNG mileage; km/kg always labelled (CNG)
    predict(page, lambda: page.goto(base + "/recommend?q=" + quote(CARD_QUERIES["cng"])))
    facts = page.locator("article.car .facts").all_inner_texts()
    bad = [f for f in facts if re.search(r"CNG mileage:\s*[\d.]+\s*kmpl", f) or re.search(r"km/kg(?! \(CNG\))", f)
           or ("Fuel: CNG" in f and "kmpl" in f)]
    check(f"{tag} [cng]: cards never show kmpl as CNG mileage; km/kg labelled (CNG)", not bad, bad[:2])
    panel = open_panel(page, 0)
    spec = panel.locator(".spec-list").first.inner_text() if panel.locator(".spec-list").count() else ""
    check(f"{tag} [cng]: panel key specs never show kmpl for a CNG variant", "CNG" in spec and "kmpl" not in spec, spec[:120])
    cng_href = panel.locator("a.detail-full").get_attribute("href")
    perm = page.context.new_page()
    car_page(perm, base + cng_href, tag, w)
    table = perm.locator("tbody tr").evaluate_all("rows => rows.map(r => [...r.cells].map(c => c.innerText.trim()))")
    bad = [r for r in table if (r[3] == "CNG" and "kmpl" in r[4]) or ("km/kg" in r[4] and "(CNG)" not in r[4])]
    check(f"{tag} [cng]: car page never shows kmpl for CNG variants; km/kg labelled (CNG)", table and not bad, bad[:2])
    perm.close()
    if shots and w in (1366, 375):
        page.locator("article.car").first.evaluate("el => el.scrollIntoView({ block: 'start', behavior: 'instant' })")
        page.wait_for_timeout(300)
        page.screenshot(path=f"{shots}/{tag.replace("/", "-")}-cng-card-panel.png")

    # Skoda Slavia: the car page reached from a search it appears in lists DCT variants as matches
    predict(page, lambda: page.goto(base + "/recommend?q=" + quote("Skoda Slavia DCT")))
    names = [c["name"] for c in page.evaluate(CARD_INFO_JS)]
    if "Skoda Slavia" in names:
        panel = open_panel(page, names.index("Skoda Slavia"))
        slavia_href = panel.locator("a.detail-full").get_attribute("href")
        if shots and w in (1366, 375):
            page.locator("article.car").nth(names.index("Skoda Slavia")).evaluate("el => el.scrollIntoView({ block: 'start', behavior: 'instant' })")
            page.wait_for_timeout(300)
            full_shot(page, f"{shots}/{tag.replace("/", "-")}-slavia-panel.png")
        perm = page.context.new_page()
        car_page(perm, base + slavia_href, tag, w)
        check(f"{tag} [slavia]: car page lists DCT variants as matches", perm.locator("tr.is-match", has_text="DCT").count() >= 1)
        perm.close()
    else:
        check(f"{tag} [slavia]: Slavia card present for 'Skoda Slavia DCT'", False, names)

    # permalink renders standalone, no JS errors
    errors = []
    perm = page.context.new_page()
    perm.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    perm.on("pageerror", lambda e: errors.append(str(e)))
    url = base + "/car/skoda/slavia?q=" + quote("DCT petrol under 15 lakh")
    resp = car_page(perm, url, tag, w)
    heads = [h for h in perm.locator("#car-detail .detail-section > h2").all_inner_texts() if h != REVIEWS_HEADING]
    check(f"{tag} [permalink]: renders standalone with every section", resp.status == 200 and heads == PAGE_HEADINGS
          and perm.locator("h1").inner_text() == "Skoda Slavia", heads)
    sw, vw = perm.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    check(f"{tag} [permalink]: no horizontal overflow", sw <= vw, f"{sw} > {vw}" if sw > vw else "")
    check(f"{tag} [permalink]: unknown car is a 404", perm.goto(base + "/car/bmw/x5").status == 404)
    check(f"{tag} [permalink]: zero JS errors", not [e for e in errors if "404" not in e], errors[:3])
    if shots and w in (1366, 375):
        perm.goto(url)
        perm.locator("#car-detail .detail-section h2").first.wait_for()
        full_shot(perm, f"{shots}/{tag.replace("/", "-")}-slavia-permalink.png")
    perm.close()


NEXON_MANY_Q = "automatic SUV under 15 lakh with sunroof"   # 22 of the Nexon's 83 variants match


def carpage_checks(ctx, base, tag, widths):
    """PR J: reviews without a search, every matching variant shown, the section menu, Add to compare, no sideways scroll."""
    page = ctx.new_page()
    for w in widths:
        t = f"{tag}@{w}"
        page.set_viewport_size({"width": w, "height": 812 if w < 600 else 860})
        # reviews on a car page opened with no search
        page.goto(base + "/car/kia/sonet")
        page.locator("#car-detail .detail-section > h2").first.wait_for(timeout=30_000)
        check(f"{t} [carpage]: /car/kia/sonet with no search shows the reviews section",
              page.locator("#detail-reviews h2").count() == 1 and page.locator("#detail-reviews .evi").count() >= 1)
        check(f"{t} [carpage]: no search -> no 'for this search' wording", "for this search" not in page.locator("#detail-reviews").inner_text())
        sw, vw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        check(f"{t} [carpage]: no horizontal page scroll (Sonet)", sw <= vw, f"{sw} > {vw}")

        # section menu
        nav = page.locator("nav[aria-label='On this page']")
        labels = nav.locator("a").all_inner_texts()
        check(f"{t} [carpage]: section menu lists Summary, Reviews, Specs, Safety, Variants",
              labels == ["Summary", "Reviews", "Specs", "Safety", "Variants"], labels)
        check(f"{t} [carpage]: menu links are real #anchors to existing sections",
              all(page.locator(href).count() == 1 for href in nav.locator("a").evaluate_all("els => els.map(e => e.getAttribute('href'))")))
        check(f"{t} [carpage]: the first link is current at the top", nav.locator("a[aria-current=true]").inner_text() == "Summary")
        page.evaluate("window.scrollTo({ top: 1500, behavior: 'instant' })")
        page.wait_for_timeout(300)
        gap = page.evaluate("() => document.querySelector('.section-menu').getBoundingClientRect().top - document.querySelector('.site-header').getBoundingClientRect().bottom")
        check(f"{t} [carpage]: the menu stays stuck under the site header after scrolling", abs(gap) <= 2, gap)
        nav.locator("a", has_text="Variants").click()
        page.wait_for_function("() => document.querySelector('.section-menu a[aria-current=true]')?.textContent === 'Variants'")
        clear = page.evaluate("""() => document.querySelector('#detail-variants h2').getBoundingClientRect().top
            - document.querySelector('.section-menu').getBoundingClientRect().bottom""")
        check(f"{t} [carpage]: clicking Variants makes it current and its heading is not under the sticky bars", clear >= 0, clear)
        sw, vw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        check(f"{t} [carpage]: menu adds no horizontal page scroll", sw <= vw, f"{sw} > {vw}")
        page.evaluate("window.scrollTo({ top: 0, behavior: 'instant' })")
        page.wait_for_function("() => document.querySelector('.section-menu a[aria-current=true]')?.textContent === 'Summary'")
        check(f"{t} [carpage]: scrolling back to the top makes Summary current again", True)

        # every matching variant shown
        page.goto(base + "/car/tata/nexon?q=" + quote(NEXON_MANY_Q))
        page.locator("#variants-table").wait_for(timeout=30_000)
        n_match = page.locator("tr.is-match").count()
        shown = page.locator("tr.is-match:not([hidden])").count()
        check(f"{t} [variants]: all {n_match} matching Nexon rows are visible without a click", n_match >= 20 and shown == n_match, f"{shown}/{n_match}")
        toggle = page.locator("[data-variants-toggle]")
        rest = page.locator("tr[data-extra]").count()
        check(f"{t} [variants]: toggle reads 'Show the other {rest} variants'", toggle.inner_text() == f"Show the other {rest} variants", toggle.inner_text())
        check(f"{t} [variants]: one legend line, no per-row badge",
              page.locator(".variants-legend").inner_text() == "Tinted rows match your search" and page.locator(".match-badge").count() == 0)
        check(f"{t} [variants]: a matching row keeps a screen-reader signal",
              "matches your search" in page.locator("tr.is-match").first.locator("td").first.text_content())
        toggle.click()
        check(f"{t} [variants]: expanding shows every row and reads 'Show matching only'",
              page.locator("tbody tr[hidden]").count() == 0 and toggle.inner_text() == "Show matching only")
        tint = page.evaluate("""() => { const bg = s => getComputedStyle(document.querySelector(s)).backgroundColor;
            return [bg('tr.is-match'), bg('tbody tr:not(.is-match):not(.is-selected)')]; }""")
        check(f"{t} [variants]: matching rows are tinted differently from the others", tint[0] != tint[1], tint)
        toggle.click()
        check(f"{t} [variants]: collapses back to 'Show the other {rest} variants'",
              page.locator("tr[data-extra]:not([hidden])").count() == 0 and toggle.inner_text() == f"Show the other {rest} variants")
        sw, vw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        check(f"{t} [variants]: no horizontal page scroll (Nexon search)", sw <= vw, f"{sw} > {vw}")

        # Add to compare
        page.goto(base + "/car/kia/sonet")
        page.evaluate("sessionStorage.clear()")
        page.goto(base + "/car/kia/sonet")
        page.locator("#variants-table").wait_for(timeout=30_000)
        btn = page.locator("[data-compare]")
        first_id = btn.get_attribute("data-compare")
        check(f"{t} [compare]: car page has 'Add to compare', not pressed", btn.inner_text() == "Add to compare" and btn.get_attribute("aria-pressed") == "false")
        btn.click()
        tray = page.locator("#compare-tray")
        check(f"{t} [compare]: the tray shows the car", tray.is_visible() and "Sonet" in tray.locator(".compare-pill").first.text_content() and btn.get_attribute("aria-pressed") == "true"
              and btn.inner_text() == "Added", tray.inner_text()[:80])   # phones list a count; the pills are still in the DOM
        row = page.locator("tbody tr:not([hidden])").filter(has_not=page.locator("[aria-pressed=true]")).first
        other_id = row.get_attribute("data-variant-id")
        other_name = row.locator(".variant-pick").inner_text()
        with page.expect_response(lambda r: "/api/car/" in r.url and "variant_id=" in r.url):
            row.click()
        page.wait_for_function("id => document.querySelector('[data-compare]').dataset.compare === id", arg=other_id)
        check(f"{t} [compare]: picking another variant moves the button to it (not pressed)",
              btn.get_attribute("aria-pressed") == "false" and btn.inner_text() == "Add to compare" and other_name in btn.get_attribute("aria-label"),
              btn.get_attribute("aria-label"))
        btn.click()
        link = tray.locator("a.btn-primary")
        href = link.get_attribute("href") if link.count() else ""
        check(f"{t} [compare]: two cars -> the tray's Compare link carries both ids", href == f"/compare?ids={first_id},{other_id}", href)
        link.click()
        page.wait_for_selector("table.compare-table")
        check(f"{t} [compare]: /compare opens with both variants", page.url.split("/compare")[1].startswith(f"?ids={first_id},{other_id}")
              and page.locator("table.compare-table").inner_text().count("Sonet") >= 1)
        # the 4-car limit: same message, button disabled
        page.goto(base + "/car/kia/sonet")
        page.evaluate("""() => sessionStorage.setItem('carrec.compare', JSON.stringify([1, 2, 3, 4].map(i => ({ variant_id: i + 1000, name: 'X', model: 'X' + i, variant: 'v' }))))""")
        page.goto(base + "/car/kia/sonet")
        page.locator("#variants-table").wait_for(timeout=30_000)
        page.locator("[data-compare]").click(force=True)  # aria-disabled, not disabled
        page.wait_for_function("() => document.getElementById('search-status').textContent.includes('up to 4 cars')")
        check(f"{t} [compare]: a fifth car is refused with the same message",
              page.locator("[data-compare]").get_attribute("aria-disabled") == "true"
              and page.locator("#search-status").inner_text() == "You can compare up to 4 cars. Remove one first.")
        page.evaluate("sessionStorage.clear()")
    page.close()


def last_turn(page):
    return page.locator("[data-turn]").last


def compare_checks(page, base, tag):
    """Select two cards -> tray -> /compare loads with both cars and no sideways page scroll; sort re-orders without a redraw."""
    predict(page, lambda: page.goto(base + "/recommend?q=" + quote("SUV under 15 lakh")))
    buttons = page.locator("[data-compare]")
    check(f"{tag}: every v3 card has a Compare button", buttons.count() == page.locator("article.car").count() > 1)
    tray = page.locator("#compare-tray")
    check(f"{tag}: tray hidden until a car is selected", tray.is_hidden())
    buttons.nth(0).click()
    check(f"{tag}: one car -> 'Pick 1 more car' and a disabled Compare", "Pick 1 more car" in tray.inner_text() and tray.locator("span[aria-disabled=true]").count() == 1)
    buttons.nth(1).click()
    check(f"{tag}: two cars -> Compare link", tray.is_visible() and tray.locator("a.btn-primary").count() == 1)
    check(f"{tag}: pressed state", buttons.nth(0).get_attribute("aria-pressed") == "true")
    names = [page.locator("article.car").nth(i).get_attribute("aria-label") for i in (0, 1)]
    tray.locator("a.btn-primary").click()
    page.wait_for_selector("table.compare-table")
    sw, vw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    check(f"{tag}: /compare has no horizontal page scroll", sw <= vw, f"{sw} > {vw}")
    body = page.inner_text("table.compare-table")
    check(f"{tag}: /compare shows both cars", all(n.split(" ", 1)[1] in body for n in names), names)
    page.go_back()
    page.wait_for_selector("article.car")
    check(f"{tag}: selection survives coming back", page.locator("#compare-tray").is_visible())
    if page.locator(".sort-seg").is_visible():
        first = page.locator("article.car").first.get_attribute("aria-label")
        page.locator(".sort-seg label", has_text="Price").first.click()
        check(f"{tag}: sort writes ?sort= and hides the rank badge", "sort=price" in page.url and page.locator(".rank").first.is_hidden())
    else:
        page.locator("select[data-sort-select]").first.select_option("price")
        check(f"{tag}: sort (select) writes ?sort=", "sort=price" in page.url)


# ---------- PR I: Back keeps your results ----------
SKELETON_WATCH = """() => {
  window.__sawSkeleton = false;
  new MutationObserver(ms => { for (const m of ms) for (const n of m.addedNodes)
    if (n.nodeType === 1 && (n.matches('.loading-steps, .skeleton') || n.querySelector('.loading-steps, .skeleton'))) window.__sawSkeleton = true;
  }).observe(document, { childList: true, subtree: true });
}"""
BLOCK_SESSION_STORAGE = "Object.defineProperty(window, 'sessionStorage', { get() { throw new DOMException('blocked', 'SecurityError'); } });"
BACK_QUERY = "SUV under 15 lakh"


def _card_labels(page):
    return page.locator("article.car").evaluate_all("els => els.map(e => e.getAttribute('aria-label') + '#' + e.dataset.variantId)")


def _settle(page):
    page.wait_for_selector("article.car")
    page.wait_for_function("!document.querySelector('.detail-body[aria-busy]')", timeout=15_000)
    page.wait_for_timeout(500)


def _prepare_view(page, compare=False):
    """search, open the second card's panel, scroll to the third card; returns (cards, scrollY)."""
    predict(page, lambda: page.goto(page._base + "/recommend?q=" + quote(BACK_QUERY)))
    cards = page.locator("article.car")
    if compare:
        page.locator("[data-compare]").nth(0).click()
        page.locator("[data-compare]").nth(1).click()
    cards.nth(1).locator("[data-detail]").click()
    page.wait_for_selector(".detail.open .detail-body:not([aria-busy])")
    page.evaluate("() => { const c = document.querySelectorAll('article.car')[2]; window.scrollTo(0, c.getBoundingClientRect().top + scrollY - 120); }")
    page.wait_for_timeout(300)
    return _card_labels(page), page.evaluate("scrollY")


def _back_view_checks(page, tag, what, labels, y, requests):
    _settle(page)
    check(f"{tag}: {what}: Back makes no /predict request", not requests, requests[:2])
    check(f"{tag}: {what}: no skeleton shown on Back", not page.evaluate("window.__sawSkeleton"))
    check(f"{tag}: {what}: same cards in the same order", _card_labels(page) == labels, _card_labels(page)[:3])
    now = page.evaluate("scrollY")
    check(f"{tag}: {what}: scroll within 50px", abs(now - y) <= 50, f"{now} vs {y}")
    check(f"{tag}: {what}: the second card's panel is still open", page.locator("article.car").nth(1).locator("[data-detail][aria-expanded=true]").count() == 1
          and page.locator(".detail.open").count() == 1)


def backcache_checks(browser, base):
    """Back keeps your results: a saved answer is drawn at once (no /predict, no skeleton), with the thread, open panels and scroll."""
    for tag, (w, h) in (("1280", (1280, 800)), ("375", (375, 812))):
        def new_page(block=False):
            ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce", color_scheme="light")
            ctx.set_default_timeout(int(os.environ.get("CARREC_GATE_TIMEOUT_MS", "60000")))
            if block:
                ctx.add_init_script(BLOCK_SESSION_STORAGE)
            ctx.add_init_script(f"({SKELETON_WATCH})()")
            page = ctx.new_page()
            page._base = base
            page._errors = []
            page.on("pageerror", lambda e: page._errors.append(str(e)))
            page._requests = []
            page.on("request", lambda r: page._requests.append(r.url) if r.url.endswith("/predict") else None)
            return ctx, page

        # car page -> Back
        ctx, page = new_page()
        labels, y = _prepare_view(page)
        page.locator("article.car").nth(2).locator(".car-title a").first.click()
        page.wait_for_url("**/car/**")
        page._requests.clear()
        page.go_back()
        _back_view_checks(page, tag, "car page", labels, y, page._requests)
        # "Back to search" on the car page: no /predict, same cards (scroll not required)
        page.locator("article.car").nth(2).locator(".car-title a").first.click()
        page.wait_for_url("**/car/**")
        page._requests.clear()
        page.locator(".back-link a").click()
        page.wait_for_selector("article.car")
        page.wait_for_timeout(600)
        check(f"{tag}: Back to search link: no /predict request", not page._requests, page._requests[:2])
        check(f"{tag}: Back to search link: no skeleton shown", not page.evaluate("window.__sawSkeleton"))
        check(f"{tag}: Back to search link: same cards in the same order", _card_labels(page) == labels)
        ctx.close()

        # compare -> Back
        ctx, page = new_page()
        labels, y = _prepare_view(page, compare=True)
        page.locator("#compare-tray a.btn-primary").click()
        page.wait_for_selector("table.compare-table")
        page._requests.clear()
        page.go_back()
        _back_view_checks(page, tag, "compare", labels, y, page._requests)
        check(f"{tag}: compare: tray still shows the selection", page.locator("#compare-tray").is_visible()
              and page.locator("[data-compare][aria-pressed=true]").count() == 2)
        ctx.close()

        # two turns -> car page -> Back keeps both turns
        ctx, page = new_page()
        predict(page, lambda: page.goto(base + "/recommend?q=" + quote(BACK_QUERY)))
        page.fill("#followupQuery", "automatic")
        predict(page, lambda: page.click("#followup button[type=submit]"))
        queries = page.locator("[data-turn]").evaluate_all("els => els.map(e => e.dataset.q)")
        turn_cards = page.locator("[data-turn]").evaluate_all("els => els.map(e => [...e.querySelectorAll('article.car')].map(c => c.dataset.variantId))")
        page.locator("[data-turn]").last.locator("article.car .car-title a").first.click()
        page.wait_for_url("**/car/**")
        page._requests.clear()
        page.go_back()
        _settle(page)
        back_turn_cards = page.locator("[data-turn]").evaluate_all("els => els.map(e => [...e.querySelectorAll('article.car')].map(c => c.dataset.variantId))")
        check(f"{tag}: two-turn thread: both turns come back", page.locator("[data-turn]").evaluate_all("els => els.map(e => e.dataset.q)") == queries and len(queries) == 2, queries)
        check(f"{tag}: two-turn thread: same cards in both turns", back_turn_cards == turn_cards)
        check(f"{tag}: two-turn thread: no /predict request", not page._requests, page._requests[:2])
        ctx.close()

        # sessionStorage that throws: search and Back still work (they search again)
        ctx, page = new_page(block=True)
        predict(page, lambda: page.goto(base + "/recommend?q=" + quote(BACK_QUERY)))
        labels = _card_labels(page)
        check(f"{tag}: storage blocked: search shows cars", len(labels) > 1)
        page.locator("article.car").nth(1).locator(".car-title a").first.click()
        page.wait_for_url("**/car/**")
        page._requests.clear()
        with page.expect_response(lambda r: r.url.endswith("/predict"), timeout=60_000):
            page.go_back()
        _settle(page)
        check(f"{tag}: storage blocked: Back searches again and shows the same cars", _card_labels(page) == labels)
        check(f"{tag}: storage blocked: no script errors", not page._errors, page._errors[:2])
        ctx.close()

        # an entry older than 30 minutes, or one for another data date, is not used
        for what, tamper in (("older than 30 minutes", "e.t -= 31 * 60 * 1000"),
                             ("different data date", "e.k = JSON.stringify(['1999-01-01|old', ...JSON.parse(e.k).slice(1)])")):
            ctx, page = new_page()
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote(BACK_QUERY)))
            labels = _card_labels(page)
            changed = page.evaluate("""() => { const l = JSON.parse(sessionStorage.getItem('carrec.results') || '[]');
                l.forEach(e => { %s; }); sessionStorage.setItem('carrec.results', JSON.stringify(l)); return l.length; }""" % tamper)
            page.locator("article.car").nth(1).locator(".car-title a").first.click()
            page.wait_for_url("**/car/**")
            with page.expect_response(lambda r: r.url.endswith("/predict"), timeout=60_000):
                page.go_back()
            _settle(page)
            check(f"{tag}: entry {what} is not used", changed >= 1 and _card_labels(page) == labels, changed)
            ctx.close()


def run(base, shots):
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for (vp_name, (w, h)), scheme in [(v, c) for v in VIEWPORTS.items() for c in SCHEMES]:
            ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="no-preference", color_scheme=scheme)
            # every action in this context (pages opened later included) waits this long; a loaded machine can starve the
            # browser past Playwright's 30 s default on a plain click. CARREC_GATE_TIMEOUT_MS overrides it.
            ctx.set_default_timeout(int(os.environ.get("CARREC_GATE_TIMEOUT_MS", "60000")))
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            tag = f"{vp_name}/{scheme}"

            # ---------- homepage ----------
            sizes, hero_status = [], {}

            def on_finished(req):
                try:
                    s = req.sizes()
                    sizes.append(s["responseBodySize"] + s["responseHeadersSize"])
                except Exception:
                    pass

            page.on("requestfinished", on_finished)
            page.on("response", lambda r: hero_status.__setitem__(r.url, r.status) if "/car_images/hero/" in r.url else None)
            page.goto(base + "/", wait_until="networkidle")
            page.wait_for_function("document.querySelectorAll('#hero-mosaic img').length > 0")
            page.wait_for_load_state("networkidle")
            visible = page.evaluate("""() => [...document.querySelectorAll('#hero-mosaic img')]
                .filter(i => i.checkVisibility()).map(i => ({ src: i.currentSrc, ok: i.complete && i.naturalWidth > 0 }))""")
            need = 12 if w >= 1024 else 6
            check(f"{tag}: hero shows >= {need} images", len(visible) >= need, len(visible))
            check(f"{tag}: every visible hero image loaded", all(v["ok"] for v in visible))
            bad_status = {u: s for u, s in hero_status.items() if s != 200}
            check(f"{tag}: hero image responses all 200", hero_status and not bad_status, bad_status or f"{len(hero_status)} fetched")
            if shots:
                page.screenshot(path=f"{shots}/{tag.replace("/", "-")}-home-top.png")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_load_state("networkidle")
            page_checks(page, f"{tag} home")
            total = sum(sizes)
            check(f"{tag}: homepage transfer < 3 MB", total < MAX_HOME_BYTES, f"{total / 1024:.0f} KB")
            if shots:
                page.locator("#how-it-works").screenshot(path=f"{shots}/{tag.replace("/", "-")}-home-how-it-works.png")
            page.remove_listener("requestfinished", on_finished)

            # homepage search box -> results page
            page.goto(base + "/")
            page.fill("#search", "CNG gaadi under 8 lakh")
            predict(page, lambda: page.click("form.search button[type=submit]"))
            check(f"{tag}: homepage search opens results", page.locator("article.car").count() > 0 and "/recommend" in page.url)

            # homepage chip click -> results
            page.goto(base + "/")
            page.wait_for_selector("[data-suggestion]")
            chip_q = page.locator("[data-suggestion]").first.get_attribute("data-suggestion")
            predict(page, lambda: page.locator("[data-suggestion]").first.click())
            q = parse_qs(urlparse(page.url).query).get("q", [""])[0]
            check(f"{tag}: home chip click -> results", q == chip_q and page.locator("[data-turn]").count() == 1)

            # ---------- results page ----------
            q = "sunroof wali SUV 12 lakh ke andar"
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote(q)))
            cards = page.locator("article.car")
            check(f"{tag}: /recommend?q= loads results", cards.count() > 0, cards.count())
            first = cards.first
            check(f"{tag}: card has photo + caption", first.locator(".car-photo img").count() == 1 and "Image:" in first.locator("figcaption").inner_text())
            # PR H: when every card meets every requirement the turn says so once above the cards; otherwise each card has its own label
            allmeet = page.locator(".all-meet")
            fits = page.locator(".fit-label").all_inner_texts()
            if allmeet.count():
                check(f"{tag}: match label, 'All N meet every requirement' once above the cards",
                      allmeet.count() == 1 and re.fullmatch(r"All \d+ meet every requirement", allmeet.inner_text().strip())
                      and int(re.search(r"\d+", allmeet.inner_text()).group()) == cards.count() and not fits
                      and page.evaluate("() => document.querySelector('.all-meet').compareDocumentPosition(document.querySelector('.cards')) & Node.DOCUMENT_POSITION_FOLLOWING") > 0,
                      allmeet.all_inner_texts())
            else:
                check(f"{tag}: match label, per-card 'Meets k of n requirements' / 'Closest match'",
                      len(fits) == cards.count() and all(re.fullmatch(r"(Meets \d+ of \d+ requirements|Confirmed on \d+ of \d+ requirements|Meets (all )?your requirements?|Ranked on your preferences|Near match|Requirements not confirmed|General pick, not personalised)", f) for f in fits),
                      fits[:3])
            reasons = [c.locator(".reasons li").count() for c in cards.all()]
            check(f"{tag}: at most 4 reasons per card", all(n <= 4 for n in reasons), reasons)
            # a feature tag that repeats a shown reason is dropped, so the sunroof is a reason ("Has sunroof, as you asked") or a tag
            check(f"{tag}: sunroof shown once, as a reason or a tag",
                  page.locator(".tag--feature", has_text="Sunroof").count() + page.locator(".reasons--v3 li", has_text=re.compile("sunroof", re.I)).count() > 0)
            vlink = first.locator("[data-variants-link]")
            check(f"{tag}: matching variants is a link to the car page's variants section",
                  vlink.count() == 1 and re.search(r"\d+ matching variants?", vlink.inner_text()) and vlink.get_attribute("href").endswith("#detail-variants")
                  and "q=" in vlink.get_attribute("href"), vlink.get_attribute("href") if vlink.count() else None)
            counts = page.locator("[data-turn-count]").first.inner_text()
            check(f"{tag}: count line under the heading", re.fullmatch(r"\d+ (closest )?cars?( · sorted by .+)?", counts) is not None, counts)
            check(f"{tag}: safety chip or no-rating chip", page.locator(".tag--safety").count() + page.locator(".tag", has_text="No crash-test rating on record").count() > 0)
            link = first.locator(".car-price a.price-link")
            check(f"{tag}: on-road price is a quiet external link under the price",
                  link.inner_text().startswith("On-road price on CarDekho") and link.get_attribute("target") == "_blank"
                  and "new tab" in link.inner_text())
            check(f"{tag}: Specs & variants is a quiet button, no filled button on the card",
                  first.locator(".car-actions .btn-quiet[data-detail]").inner_text() == "Specs & variants" and first.locator(".car-actions .btn-primary").count() == 0)
            check(f"{tag}: results thread is not a live region", page.locator("#results[aria-live]").count() == 0)
            check(f"{tag}: data stamp", page.locator(".data-stamp").count() == 1)
            check(f"{tag}: copy link button", page.locator("[data-copy-link]").count() == 1)
            page_checks(page, f"{tag} results")
            if shots:
                full_shot(page, f"{shots}/{tag.replace("/", "-")}-results-sunroof.png")

            card_checks(page, base, tag, w, shots)
            detail_checks(page, base, tag, w, shots)
            compare_checks(page, base, tag)
            if vp_name != "desktop":   # PR J: 1280 (from the laptop run), 375 and 320 (from the phone run)
                carpage_checks(ctx, base, tag, [1280] if w >= 1000 else [375, 320])

            # transmission label
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote("DCT petrol under 15 lakh")))
            check(f"{tag}: transmission label 'Automatic (DCT)'", page.locator(".facts", has_text="Automatic (DCT)").count() > 0)

            # an unverified requirement is named on the card and the label says so ("Confirmed on 1 of 2 requirements")
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote("5 star safety sedan")))
            confirmed = [c for c in page.evaluate(CARD_INFO_JS) if re.fullmatch(r"Confirmed on \d+ of \d+ requirements", c["fit"])]
            check(f"{tag}: unverified requirement -> 'Confirmed on k of n' label + 'Not verified: ...' line",
                  confirmed and page.locator(".unmet li", has_text="Not verified:").count() > 0, len(confirmed))
            check(f"{tag}: Bharat NCAP safety chip", page.locator(".tag--safety", has_text="Bharat NCAP").count() > 0)

            # nothing matches everything: closest cars, per-card 'Meets k of n', 'Closest match' badge, drop hints
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote("CVT automatic hatchback under 5 lakh")))
            rc = page.evaluate(CARD_INFO_JS)
            check(f"{tag}: unverified chip style", page.locator(".tag--unverified").count() > 0)
            check(f"{tag}: relaxed search -> notice, hints, 'Closest match' badge, 'Meets k of n requirements', 'Not met' lines",
                  "No car matches everything" in page.locator(".notice").inner_text() and page.locator("[data-drop-key]").count() > 0
                  and rc[0]["rank"] == "Closest match" and all(re.fullmatch(r"Meets \d+ of \d+ requirements", c["fit"]) for c in rc)
                  and page.locator(".unmet li", has_text="Not met:").count() > 0 and not page.locator(".all-meet").count(),
                  [(c["rank"], c["fit"]) for c in rc[:2]])
            check(f"{tag}: count line says 'closest cars' for a relaxed search",
                  re.fullmatch(r"\d+ closest cars?( · sorted by .+)?", page.locator("[data-turn-count]").first.inner_text()) is not None)
            if shots:
                page.screenshot(path=f"{shots}/{tag.replace('/', '-')}-relaxed-cvt.png", full_page=True)
            predict(page, lambda: page.locator("[data-drop-key]").first.click())
            lt = last_turn(page)
            check(f"{tag}: hint click -> results + 'Showing results without' banner",
                  lt.locator("article.car").count() > 0 and "Showing results without" in lt.locator(".dropped").inner_text()
                  and "drop=" in page.url)

            # unsupported brand banner
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote("BMW SUV")))
            check(f"{tag}: unsupported-brand banner", "We don't cover BMW" in page.locator(".notice").inner_text())
            if shots:
                page.screenshot(path=f"{shots}/{tag.replace("/", "-")}-bmw-banner.png")

            # thread: 3 queries -> 3 turns, back/forward, New search, chips in the follow-up box
            page.goto(base + "/recommend")
            page.fill("#userQuery", "7 seater under 15 lakh")
            predict(page, lambda: page.click(".search-form:not(#followup) button[type=submit]"))
            check(f"{tag}: follow-up box appears", page.locator("#followup").is_visible())
            page.fill("#followupQuery", "EV under 15 lakh")
            predict(page, lambda: page.click("#followup button[type=submit]"))
            if shots:
                full_shot(page, f"{shots}/{tag.replace("/", "-")}-thread-2-turns.png")
            page.wait_for_selector("#followup [data-suggestion]")
            # a chip that repeats the current search replaces the history entry instead of adding one
            chip = page.locator("#followup [data-suggestion]:not([data-suggestion='EV under 15 lakh'])").first
            predict(page, lambda: chip.click())
            check(f"{tag}: 3 queries -> 3 turns", page.locator("[data-turn]").count() == 3)
            page.go_back()
            page.wait_for_timeout(400)
            q_back = parse_qs(urlparse(page.url).query).get("q", [""])[0]
            check(f"{tag}: back -> previous search in URL, thread kept", q_back == "EV under 15 lakh" and page.locator("[data-turn]").count() == 3, q_back)
            page.go_forward()
            page.wait_for_timeout(400)
            check(f"{tag}: forward", parse_qs(urlparse(page.url).query).get("q", [""])[0] != "EV under 15 lakh")
            page.click("[data-new-search]")
            check(f"{tag}: New search clears", page.locator("[data-turn]").count() == 0 and not page.locator("#followup").is_visible() and "q=" not in page.url)

            # 10-turn cap + More ideas
            page.fill("#userQuery", "EV under 15 lakh")
            predict(page, lambda: page.click(".search-form:not(#followup) button[type=submit]"))
            for i in range(10):
                page.fill("#followupQuery", f"automatic under {10 + i} lakh")
                predict(page, lambda: page.click("#followup button[type=submit]"))
            check(f"{tag}: 10-turn cap", page.locator("[data-turn]").count() == 10)
            # on phones the top box hides its chips once there are turns (PR H); the follow-up box keeps its own More ideas
            top = page.locator(".search-form:not(#followup)")
            scope = top if top.locator("[data-more-ideas]").is_visible() else page.locator("#followup")
            before = scope.locator("[data-suggestion]").all_inner_texts()
            scope.locator("[data-more-ideas]").click()
            after = scope.locator("[data-suggestion]").all_inner_texts()
            check(f"{tag}: More ideas rotates chips", before != after)

            # body-type placeholder (a model with no brochure image)
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote("Mahindra Thar Roxx")))
            srcs = page.locator(".car-photo img").evaluate_all("els => els.map(e => e.getAttribute('src'))")
            if any(s.endswith(".svg") for s in srcs):
                check(f"{tag}: body-type placeholder renders", True)
            else:
                print(f"INFO  {tag}: no placeholder in this result set ({srcs[:2]})")

            # coming-soon / used page renders cleanly
            page.goto(base + "/used")
            page_checks(page, f"{tag} used")

            check(f"{tag}: zero console errors", not errors, errors[:3])
            ctx.close()
        backcache_checks(browser, base)
        browser.close()


if __name__ == "__main__":
    base = sys.argv[1].rstrip("/")
    shots = None
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        Path(shots).mkdir(parents=True, exist_ok=True)
    run(base, shots)
    failed = [n for n, ok in results if not ok]
    for t in dict.fromkeys(n.split(":")[0].split(" ")[0] for n, _ in results):
        mine = [ok for n, ok in results if n.split(":")[0].split(" ")[0] == t]
        print(f"{t}: {sum(mine)} PASS, {len(mine) - sum(mine)} FAIL")
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)
