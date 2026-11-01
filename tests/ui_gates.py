"""Browser gates for the UI (not collected by pytest; needs Playwright + Chromium).

    python tests/ui_gates.py http://127.0.0.1:5077 [--shots DIR]

Runs every user flow at 1440x900, 1366x860 and 390x844 and prints one PASS/FAIL line per check.
Exit status 1 if any check fails.
"""

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from playwright.sync_api import sync_playwright

VIEWPORTS = {"desktop": (1440, 900), "laptop": (1366, 860), "mobile": (390, 844)}
MAX_CARD_HEIGHT = 340
CARD_QUERIES = {"sunroof": "sunroof wali SUV 12 lakh ke andar", "cng": "CNG gaadi under 8 lakh", "ev": "EV under 15 lakh"}
BUDGET_REASON = re.compile(r"₹[\d.]+L under your budget|Right at your budget")
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
        reasons: [...c.querySelectorAll('.reasons li')].map(li => li.innerText.trim()),
        chips: [...c.querySelectorAll('.tag')].map(t => t.innerText.trim()),
    };
})"""


def card_checks(page, base, tag, w, shots):
    for key, q in CARD_QUERIES.items():
        predict(page, lambda: page.goto(base + "/recommend?q=" + quote(q)))
        cards = page.evaluate(CARD_INFO_JS)
        check(f"{tag} [{key}]: has cards", cards, len(cards))
        if w >= 1024:
            heights = [c["height"] for c in cards]
            check(f"{tag} [{key}]: every card <= {MAX_CARD_HEIGHT}px tall", all(h <= MAX_CARD_HEIGHT for h in heights), heights)
            check(f"{tag} [{key}]: photo left of content", all(c["photoLeft"] for c in cards))
        else:
            check(f"{tag} [{key}]: photo above content", all(c["photoAbove"] for c in cards))
        sw, vw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        check(f"{tag} [{key}]: no horizontal overflow", sw <= vw, f"{sw} > {vw}" if sw > vw else "")
        dupes = [(c["name"], r, ch) for c in cards for r in c["reasons"] for ch in c["chips"]
                 if r.lower() in ch.lower() or ch.lower() in r.lower()]
        check(f"{tag} [{key}]: no reason duplicates a chip", not dupes, dupes[:3])
        if w == 1366:
            page.locator("article.car").first.evaluate("el => el.scrollIntoView({ block: 'start' })")
            page.wait_for_timeout(300)
            full = page.evaluate("""() => {
                const top = document.querySelector('.site-header').getBoundingClientRect().bottom;
                return [...document.querySelectorAll('article.car')].filter(c => {
                    const r = c.getBoundingClientRect(); return r.top >= top - 1 && r.bottom <= innerHeight + 1;
                }).length;
            }""")
            check(f"{tag} [{key}]: >= 2 full cards visible after scrolling the first to the top", full >= 2, full)
        if key == "cng":
            kmkg = [c for c in cards if "km/kg" in c["facts"]]
            check(f"{tag} [cng]: a card shows km/kg", kmkg, len(kmkg))
            # cards whose response has mileage_km_per_kg must never say Not listed
            data = page.evaluate("q => fetch('/predict', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query: q})}).then(r => r.json())", q)
            have = {f"{r['Make']} {r['Model']}" for r in data["recommendations"] if r.get("mileage_km_per_kg")}
            bad = [c["name"] for c in cards if c["name"] in have and ("Not listed" in c["facts"] or "km/kg" not in c["facts"])]
            check(f"{tag} [cng]: km/kg shown wherever it exists", have and not bad, bad or f"{len(have)} with km/kg")
        if key == "ev":
            bad = [c["facts"] for c in cards if not re.search(r"Range: \d+ km", c["facts"])]
            check(f"{tag} [ev]: every card shows 'Range: <n> km'", not bad, bad[:2])
        if key == "sunroof":
            echo = [r for c in cards for r in c["reasons"] if re.search("suv|sunroof", r, re.I)]
            check(f"{tag} [sunroof]: no reason mentions SUV or sunroof", not echo, echo[:3])
            budget = [r for c in cards for r in c["reasons"] if "budget" in r.lower()]
            check(f"{tag} [sunroof]: budget reasons are headroom", budget and all(BUDGET_REASON.fullmatch(r) for r in budget), budget[:3])
            check(f"{tag} [sunroof]: no bare 'Fits your budget'", not any("fits your" in r.lower() for c in cards for r in c["reasons"]))
            print(f"INFO  {tag} [sunroof] reasons: " + " | ".join(f"{c['name']}: {c['reasons']}" for c in cards))
        if shots and w in (1366, 390):
            full_shot(page, f"{shots}/{tag}-{key}.png")


def last_turn(page):
    return page.locator("[data-turn]").last


def run(base, shots):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp_name, (w, h) in VIEWPORTS.items():
            ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="no-preference")
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            tag = vp_name

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
                page.screenshot(path=f"{shots}/{tag}-home-top.png")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_load_state("networkidle")
            page_checks(page, f"{tag} home")
            total = sum(sizes)
            check(f"{tag}: homepage transfer < 3 MB", total < MAX_HOME_BYTES, f"{total / 1024:.0f} KB")
            if shots:
                page.locator("#how-it-works").screenshot(path=f"{shots}/{tag}-home-how-it-works.png")
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
            labels = page.locator(".match").all_inner_texts()
            check(f"{tag}: match labels", labels and all(l in ("Great match", "Good match", "Fair match") for l in labels), labels[:3])
            reasons = [c.locator(".reasons li").count() for c in cards.all()]
            check(f"{tag}: at most 4 reasons per card", all(n <= 4 for n in reasons), reasons)
            check(f"{tag}: feature chip (Sunroof)", page.locator(".tag--feature", has_text="Sunroof").count() > 0)
            check(f"{tag}: matching_variant_count chip", page.locator(".tag", has_text=re.compile(r"\d+ matching variants?")).count() > 0)
            check(f"{tag}: safety chip or no-rating chip", page.locator(".tag--safety").count() + page.locator(".tag", has_text="No Bharat NCAP rating on record").count() > 0)
            link = first.locator(".car-actions a")
            check(f"{tag}: primary action is external on-road price link",
                  link.inner_text().startswith("Check on-road price") and link.get_attribute("target") == "_blank"
                  and "new tab" in link.inner_text())
            check(f"{tag}: data stamp", page.locator(".data-stamp").count() == 1)
            check(f"{tag}: copy link button", page.locator("[data-copy-link]").count() == 1)
            page_checks(page, f"{tag} results")
            if shots:
                full_shot(page, f"{shots}/{tag}-results-sunroof.png")

            card_checks(page, base, tag, w, shots)

            # transmission label
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote("DCT petrol under 15 lakh")))
            check(f"{tag}: transmission label 'Automatic (DCT)'", page.locator(".facts", has_text="Automatic (DCT)").count() > 0)

            # unverified chips somewhere in a broad result set
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote("5 star safety sedan")))
            check(f"{tag}: unverified chip style", page.locator(".tag--unverified").count() > 0)
            check(f"{tag}: Bharat NCAP safety chip", page.locator(".tag--safety", has_text="Bharat NCAP").count() > 0)

            # empty state + hint click -> results + banner
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote("CVT automatic hatchback")))
            check(f"{tag}: empty state with hints", page.locator(".state h3").count() == 1 and page.locator("[data-drop-key]").count() > 0)
            if shots:
                page.screenshot(path=f"{shots}/{tag}-empty-cvt.png", full_page=True)
            predict(page, lambda: page.locator("[data-drop-key]").first.click())
            lt = last_turn(page)
            check(f"{tag}: hint click -> results + 'Showing results without' banner",
                  lt.locator("article.car").count() > 0 and "Showing results without" in lt.locator(".dropped").inner_text()
                  and "drop=" in page.url)

            # unsupported brand banner
            predict(page, lambda: page.goto(base + "/recommend?q=" + quote("BMW SUV")))
            check(f"{tag}: unsupported-brand banner", "We don't cover BMW" in page.locator(".notice").inner_text())
            if shots:
                page.screenshot(path=f"{shots}/{tag}-bmw-banner.png")

            # thread: 3 queries -> 3 turns, back/forward, New search, chips in the follow-up box
            page.goto(base + "/recommend")
            page.fill("#userQuery", "7 seater under 15 lakh")
            predict(page, lambda: page.click(".search-form:not(#followup) button[type=submit]"))
            check(f"{tag}: follow-up box appears", page.locator("#followup").is_visible())
            page.fill("#followupQuery", "EV under 15 lakh")
            predict(page, lambda: page.click("#followup button[type=submit]"))
            if shots:
                full_shot(page, f"{shots}/{tag}-thread-2-turns.png")
            page.wait_for_selector("#followup [data-suggestion]")
            predict(page, lambda: page.locator("#followup [data-suggestion]").first.click())
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
            before = page.locator(".search-form:not(#followup) [data-suggestion]").all_inner_texts()
            page.locator(".search-form:not(#followup) [data-more-ideas]").click()
            after = page.locator(".search-form:not(#followup) [data-suggestion]").all_inner_texts()
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
        browser.close()


if __name__ == "__main__":
    base = sys.argv[1].rstrip("/")
    shots = None
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        Path(shots).mkdir(parents=True, exist_ok=True)
    run(base, shots)
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)
