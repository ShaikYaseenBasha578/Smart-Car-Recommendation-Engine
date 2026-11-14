"""Autocar India expert-review page parser (/cars/{make}/{model}/expert-reviews).

Where things sit (REVIEW_PAGE_INSPECTION.md): overall score and review date in JSON-LD (`Review.reviewRating`,
`datePublished`), the same overall plus seven aspect scores out of 10 in the markup, pros/cons under #pros-and-cons,
some aspects with a prose paragraph. No LLM here: numbers only. Returns None for an unreadable page."""
import html
import json
import re

NAME = "autocar"
BASE = "https://www.autocarindia.com"
SCALE = 10.0
# the publisher's own labels, as written in the markup (title case), and the labels used in the KB
ASPECTS = ["Exterior Design And Engineering", "Interior Space And Comfort", "Performance And Refinement",
           "Mileage / Range And Efficiency", "Ride Comfort And Handling", "Features And Safety", "Value For Money"]
MAKE_SLUG = {"Maruti Suzuki": "maruti-suzuki", "MG": "mg"}


def make_slug(make):
    return MAKE_SLUG.get(make) or re.sub(r"[^a-z0-9]+", "-", make.lower()).strip("-")


def url(make_s, model_s):
    return "%s/cars/%s/%s/expert-reviews" % (BASE, make_s, model_s)


def _text(s):
    s = re.sub(r"<svg.*?</svg>", "", s, flags=re.S)
    s = re.sub(r"<(/p|/li|/h\d|/div|/span)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"[ \t]*\n[\s]*", "\n", html.unescape(s)).strip()


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(s or "").lower()).strip()


def _num(s):
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


def _jsonld(page):
    out = []
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            out.append(json.loads(m.group(1)))
        except ValueError:
            pass
    return out


def _reviews(o, acc):
    if isinstance(o, dict):
        if o.get("@type") == "Review" and isinstance(o.get("reviewRating"), dict):
            acc.append(o)
        for v in o.values():
            _reviews(v, acc)
    elif isinstance(o, list):
        for v in o:
            _reviews(v, acc)
    return acc


def parse(page):
    """{page_name, canonical, ld_overall, ld_best, published_on, last_updated, overall, aspects{label: score},
        pros[], cons[], aspect_text{label: text}} or None."""
    if not page or "autocarindia" not in page[:200000].lower():
        return None
    r = {"page_name": None, "canonical": None, "ld_overall": None, "ld_best": None, "published_on": None,
         "last_updated": None, "overall": None, "aspects": {}, "pros": [], "cons": [], "aspect_text": {}}
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    r["page_name"] = re.sub(r"\s*Expert Review\s*$", "", _text(m.group(1)), flags=re.I) if m else None
    m = re.search(r'rel="canonical" href="([^"]+)"', page)
    r["canonical"] = m.group(1) if m else None
    cands = []
    for blk in _jsonld(page):
        cands += _reviews(blk, [])
    if cands:
        want = norm(r["page_name"])
        rv = next((c for c in cands if want and norm((c.get("itemReviewed") or {}).get("name")) == want), cands[0])
        rr = rv["reviewRating"]
        r["ld_overall"], r["ld_best"] = _num(rr.get("ratingValue")), _num(rr.get("bestRating"))
        r["published_on"] = (rv.get("datePublished") or "")[:10] or None
        r["ld_name"] = (rv.get("itemReviewed") or {}).get("name")
    m = re.search(r"Last Updated on:\s*(?:<!--\s*-->)?\s*([0-9]{1,2} [A-Za-z]{3} [0-9]{4})", page)
    r["last_updated"] = m.group(1) if m else None
    m = re.search(r'Autocar score</div><div[^>]*><span[^>]*>([0-9.]+)</span>', page)
    r["overall"] = _num(m.group(1)) if m else None
    pos = []
    for label in ASPECTS:
        m = re.search(re.escape(label) + r'</span><div class="relative flex size-8[^>]*>.*?<p class="text-\[10px\] font-semibold">([0-9.]+)</p>', page, re.S)
        if m:
            r["aspects"][label] = _num(m.group(1))
            pos.append((m.start(), label, m.end()))
    pos.sort()
    for i, (p0, label, p1) in enumerate(pos):
        end = pos[i + 1][0] if i + 1 < len(pos) else p1 + 6000
        mm = re.search(r'<div class="styledInnerHTML[^"]*"[^>]*>(.*?)</div>', page[p1:end], re.S)
        if mm:
            t = _text(mm.group(1))
            if t:
                r["aspect_text"][label] = t
    i = page.find('id="pros-and-cons"')
    if i >= 0:
        seg = page[i:i + 8000].split(">", 1)[-1]
        stop = seg.find("Expert Review</h2>")
        lines = [l.strip() for l in _text(seg[:stop] if stop > 0 else seg).split("\n") if l.strip()]
        cur = None
        for l in lines:
            low = l.lower()
            if low == "we like":
                cur = "pros"
            elif low in ("we don't like", "we dont like"):
                cur = "cons"
            elif cur and "expert review" in low:
                break
            elif cur and "pros and cons" not in low and low != "see more" and norm(l) != norm(r["page_name"]):
                r[cur].append(l)
    return r


def text_blob(parsed):
    """The page text the notes are read from and checked against."""
    parts = []
    if parsed["pros"]:
        parts.append("We like: " + "; ".join(parsed["pros"]))
    if parsed["cons"]:
        parts.append("We don't like: " + "; ".join(parsed["cons"]))
    for label, t in parsed["aspect_text"].items():
        parts.append("%s: %s" % (label, t[:900]))
    return "\n".join(parts)
