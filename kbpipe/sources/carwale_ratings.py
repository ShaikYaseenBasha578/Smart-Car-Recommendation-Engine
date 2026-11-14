"""CarWale user-reviews page parser (/{make}-cars/{model}/user-reviews/ and /reviews/page/N/).

The numbers and the first ten written reviews sit in <script id="initial-state">, key userReviewListing
(REVIEW_PAGE_INSPECTION.md). Plain fetches only; no script-loaded endpoint. Returns None for an unreadable page."""
import html
import json
import re

NAME = "carwale"
BASE = "https://www.carwale.com"
SCALE = 5.0
# rating questions on the page (QuestionId -> label); the other questions in the same list are not ratings
ASPECT_IDS = {133: "Design and Styling", 134: "Comfort and Space", 135: "Performance", 136: "Fuel Economy",
              137: "Value for Money", 240: "Features and Technology", 242: "After Sales Cost and Experience"}
ASPECTS = list(ASPECT_IDS.values())


def make_slug(make):
    from .carwale import MAKE_SLUG
    return MAKE_SLUG.get(make) or re.sub(r"[^a-z0-9]+", "-", make.lower()).strip("-")


def url(make_s, model_s, page=1):
    base = "%s/%s-cars/%s/" % (BASE, make_s, model_s)
    return base + "user-reviews/" if page == 1 else base + "reviews/page/%d/" % page


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(s or "").lower()).strip()


def state(page):
    m = re.search(r'<script[^>]*id="initial-state"[^>]*>(.*?)</script>', page or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        try:
            return json.loads(html.unescape(m.group(1)))
        except ValueError:
            return None


def _reviews(lst):
    out = []
    for r in lst or []:
        text = (r.get("Description") or "").strip()
        if not text:
            continue
        ri, vi = r.get("RatingInfo") or {}, r.get("VehicleInfo") or {}
        out.append({"id": r.get("Id"), "title": (r.get("Title") or "").strip(), "text": text,
                    "rating": ri.get("UserRating"), "version_id": vi.get("VersionId"),
                    "entry": r.get("LastUpdatedOn") or r.get("EntryDate")})
    return out


def parse(page):
    """{make, model, model_id, overall, rating_count, review_count, aspects{label: score}, reviews[], total_reviews} or None."""
    s = state(page)
    u = (s or {}).get("userReviewListing")
    if not u or "aggregateRating" not in u:
        return None
    a, md = u["aggregateRating"], u.get("modelDetails") or {}
    rl = u.get("userReviewList") or {}
    r = {"make": (md.get("makeName") or "").strip(), "model": (md.get("modelName") or "").strip(),
         "model_id": (a.get("vehicleInfo") or {}).get("ModelId"), "overall": a.get("overallRating"),
         "rating_count": a.get("totalRatings"), "review_count": (a.get("reviewCount") or {}).get("total"),
         "aspects": {}, "reviews": _reviews(rl.get("Reviews")), "total_reviews": rl.get("TotalRecordCount")}
    for p in a.get("reviewParameters") or []:
        if p.get("QuestionId") in ASPECT_IDS and isinstance(p.get("Answer"), (int, float)):
            r["aspects"][ASPECT_IDS[p["QuestionId"]]] = round(float(p["Answer"]), 2)
    return r


def parse_reviews_only(page):
    p = parse(page)
    return p["reviews"] if p else None
