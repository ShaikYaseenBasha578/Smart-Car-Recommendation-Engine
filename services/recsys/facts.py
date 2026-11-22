"""Facts for grounded explanations (plan C). Deterministic, no network, no LLM.

`build_facts(card, row, requirements)` lists, for ONE recommended car, only what the engine used or shows for it: spec
cells, stored expert notes and quotes, owner themes and ratings, the crash-test row, price, the query requirements the
car meets and the ones that are not confirmed. Each fact gets a stable id f1..fN (fixed assembly order, so the same car
and the same data always give the same ids) and a set of numeric tokens, which is what the checker in rag_explain.py
compares a generated sentence against. Unknowns are facts too ("Unknown: mileage"): a sentence may say a value is not
on record, and it may not say anything else about it.

Fact kinds: identity, price, spec, features, query, requirement, ncap, unknown_ncap, expert, owner, caveat,
standing (compares the car with its segment), score (a template reason that ranks the car against similar ones),
unknown.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from services.recsys.common import is_unknown, num
from services.recsys.criteria import COMFORT_BOOLS, TECH_BOOLS
from services.recsys.explain import BOOL_LABELS
from services.recsys.relax import format_rupees

# ---------------------------------------------------------------- numeric tokens (shared with the checker)

UNIT_CLASS = {
    "lakh": "money", "lakhs": "money", "lac": "money", "lacs": "money", "crore": "money", "crores": "money", "cr": "money",
    "km/kg": "km/kg", "km/l": "kmpl", "kmpl": "kmpl", "km": "km", "kms": "km", "bhp": "bhp", "ps": "bhp", "nm": "nm",
    "l": "litres", "litre": "litres", "litres": "litres", "liter": "litres", "liters": "litres", "mm": "mm",
    "star": "stars", "stars": "stars", "airbag": "airbags", "airbags": "airbags", "seat": "seats", "seats": "seats",
    "seater": "seats", "seaters": "seats", "year": "years", "years": "years", "%": "percent", "review": "count",
    "reviews": "count", "rating": "count", "ratings": "count", "post": "count", "posts": "count", "cc": "cc",
}
_UNITS = sorted(UNIT_CLASS, key=len, reverse=True)
_UNIT_RE = "|".join(re.escape(u) for u in _UNITS)
NUM_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?P<cur>₹\s*|rs\.?\s*)?(?P<num>\d+(?:,\d+)*(?:\.\d+)?)(?:\s*(?:-\s*)?(?P<unit>" + _UNIT_RE
    + r")(?![A-Za-z]))?", re.IGNORECASE)
WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "eleven": 11, "twelve": 12}
WORD_NUM_RE = re.compile(r"\b(" + "|".join(WORD_NUMBERS) + r")(?:\s*-\s*|\s+)(" + _UNIT_RE + r")(?![A-Za-z])", re.IGNORECASE)
# a number shaped like "8/10" is two numbers (score and scale); both are matched on their own
MONEY_SCALE = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7}
MONEY_TOLERANCE = {"lakh": 500.0, "lakhs": 500.0, "lac": 500.0, "lacs": 500.0, "crore": 50000.0, "crores": 50000.0,
                   "cr": 50000.0}


def numeric_tokens(text: str) -> List[Tuple[float, Optional[str], float]]:
    """[(value, unit class or None, tolerance)] for every number in `text`. Lakh / crore and "₹" amounts are
    normalised to rupees (class "money"); thousands separators (also Indian grouping) are removed. `tolerance` is the
    rounding a figure written in lakh may carry (two decimals of a lakh)."""
    out: List[Tuple[float, Optional[str], float]] = []
    for m in NUM_RE.finditer(text or ""):
        value = float(m.group("num").replace(",", ""))
        unit = (m.group("unit") or "").lower()
        cls = UNIT_CLASS.get(unit)
        tol = 0.0
        if unit in MONEY_SCALE:
            value *= MONEY_SCALE[unit]
            tol = MONEY_TOLERANCE[unit]
        if m.group("cur"):
            cls = cls or "money"
        out.append((value, cls, tol))
    for m in WORD_NUM_RE.finditer(text or ""):
        out.append((float(WORD_NUMBERS[m.group(1).lower()]), UNIT_CLASS.get(m.group(2).lower()), 0.0))
    return out


def token_matches(token: Tuple[float, Optional[str], float], fact_tokens: Iterable[Tuple[float, Optional[str]]]) -> bool:
    value, cls, tol = token
    for fv, fcls in fact_tokens:
        if cls is not None and fcls is not None and cls != fcls:
            continue
        if abs(fv - value) <= max(tol, 1e-9 * max(1.0, abs(value))):
            return True
    return False


# ---------------------------------------------------------------- facts

@dataclass
class Fact:
    id: str
    kind: str
    label: str                      # short label shown next to the citation
    text: str                       # exactly what the model sees and what the checker reads
    source: Optional[str] = None
    url: Optional[str] = None
    date: Optional[str] = None
    tokens: List[Tuple[float, Optional[str]]] = field(default_factory=list)

    def public(self) -> dict:
        return {"label": self.label, "source": self.source, "source_url": self.url, "date": self.date}


NCAP_KINDS = ("ncap", "unknown_ncap")
COMPARING_KINDS = ("standing", "score")
MAX_FACTS = 40


def _unit_line(card: dict, row) -> List[Tuple[str, str]]:
    """(label, text) pairs for spec cells the card or the row carries."""
    def val(name, card_key=None):
        v = card.get(card_key) if card_key and not is_unknown(card.get(card_key)) else None
        if v is None and row is not None and name in row.index:
            v = num(row[name])
        return None if is_unknown(v) else v

    specs: List[Tuple[str, str]] = []

    def add(label, v, fmt):
        if v is not None:
            specs.append((label, fmt.format(v)))

    fuel = card.get("Fuel_Type")
    if fuel:
        specs.append(("Fuel", f"Fuel: {fuel}"))
    if card.get("transmission_label"):
        specs.append(("Gearbox", f"Gearbox: {card['transmission_label']}"))
    if row is not None and "body_type" in row.index and not is_unknown(row["body_type"]):
        specs.append(("Body type", f"Body type: {row['body_type']}"))
    add("Seats", val("seats"), "Seats: {:g} seats")
    add("Engine", val("engine_cc", "Displacement"), "Engine: {:g} cc")
    add("Power", val("power_bhp", "power_bhp"), "Power: {:g} bhp")
    add("Torque", val("torque_nm"), "Torque: {:g} Nm")
    add("Mileage", card.get("ARAI_Certified_Mileage") if not is_unknown(card.get("ARAI_Certified_Mileage")) else None,
        "Mileage (ARAI): {:g} km/l")
    add("Mileage (CNG)", card.get("mileage_km_per_kg"), "Mileage (ARAI): {:g} km/kg")
    add("Range", card.get("ev_range_km"), "Range: {:g} km")
    add("Boot", val("boot_space_litres", "boot_space_litres"), "Boot space: {:g} litres")
    add("Wheelbase", val("wheelbase_mm"), "Wheelbase: {:g} mm")
    add("Ground clearance", val("ground_clearance_mm"), "Ground clearance: {:g} mm")
    add("Airbags", val("airbags", "airbags"), "Airbags: {:g} airbags")
    return specs


def _unknown_cells(card: dict, row) -> List[Tuple[str, str]]:
    out = []
    fuel = card.get("Fuel_Type") or ""
    fuel_l = str(fuel).lower()
    if "electric" in fuel_l and "hybrid" not in fuel_l:
        if is_unknown(card.get("ev_range_km")):
            out.append(("Range", "Unknown: range"))
    elif "cng" in fuel_l:
        if is_unknown(card.get("mileage_km_per_kg")):
            out.append(("Mileage", "Unknown: mileage"))
    elif is_unknown(card.get("ARAI_Certified_Mileage")):
        out.append(("Mileage", "Unknown: mileage"))
    if is_unknown(card.get("power_bhp")):
        out.append(("Power", "Unknown: power"))
    if is_unknown(card.get("airbags")):
        out.append(("Airbags", "Unknown: airbag count"))
    if is_unknown(card.get("boot_space_litres")):
        out.append(("Boot", "Unknown: boot space"))
    return out


def _date(text: Any) -> Optional[str]:
    t = None if text is None or is_unknown(text) else str(text)[:10]
    return t or None


def build_facts(card: dict, row=None, requirements: Optional[List[str]] = None) -> List[Fact]:
    """The fact list of one car. `card` is the response card, `row` the catalogue row (optional, adds spec cells the
    card does not carry), `requirements` the plain-words requirement phrases of the query."""
    items: List[dict] = []

    def add(kind, label, text, source=None, url=None, date=None):
        items.append({"kind": kind, "label": label, "text": text, "source": source, "url": url or None, "date": date})

    add("identity", "Car", f"Car: {card['Make']} {card['Model']} {card['Variant']}")
    price = num(card.get("Ex-Showroom_Price"))
    if price is not None:
        add("price", "Price", f"Ex-showroom price: {format_rupees(price)} (₹{int(round(price)):,})")
    else:
        add("unknown", "Price", "Unknown: price")
    for label, text in _unit_line(card, row):
        add("spec", label, text, source="CarRec catalogue")
    if row is not None:
        for name, cols in (("Comfort features", COMFORT_BOOLS), ("Tech and driver-assist features", TECH_BOOLS)):
            have = [BOOL_LABELS[c] for c in cols if c in row.index and row[c] is True and c in BOOL_LABELS]
            if have:
                add("features", name, f"{name} on record: {', '.join(have)}", source="CarRec catalogue")
    for label, text in _unknown_cells(card, row):
        add("unknown", label, text)

    if requirements:
        add("query", "Your query", "Your query asked for: " + "; ".join(requirements))
    for f in card.get("matched_features") or []:
        add("requirement", "Requirement met", f"Requirement met: {str(f).replace('_', ' ')}")
    for u in card.get("not_verified") or []:
        add("unknown_ncap" if "crash" in str(u).lower() else "unknown", "Not confirmed", f"Unknown: {u}")
    for f in card.get("missing_features") or []:
        add("unknown", "Not confirmed", f"Unknown: {str(f).replace('_', ' ')} is not confirmed for this variant")

    s = card.get("safety")
    if s:
        child = f", child {s['stars_child']} stars" if s.get("stars_child") is not None else ""
        year = f", tested {s['year']}" if s.get("year") else ""
        body = s.get("testing_body") or "crash test"
        add("ncap", "Crash-test rating", f"Crash-test rating ({body}): adult {s['stars_adult']} stars{child}{year}",
            source=body)
    else:
        add("unknown_ncap", "Crash-test rating", "Unknown: crash-test rating (none on record)")

    for n in card.get("expert_notes") or []:
        text = n["text"]
        q = n.get("quote")
        if q and q.get("text"):
            text += f' Quote: "{q["text"]}"'
        add("expert", n.get("source_aspect") or "Expert note", text, source=n.get("source"), url=n.get("source_url"),
            date=_date(n.get("published_on")))
    seen = set()
    for n in (card.get("owner_notes") or []):
        seen.add(n["text"])
        add("owner", "Owner reviews", n["text"], source=n.get("source"), url=n.get("source_url"))
    for n in card.get("caveats") or []:
        if n["text"] not in seen:
            add("caveat", "Owner reviews", n["text"], source=n.get("source"), url=n.get("source_url"))
    es, os_ = card.get("expert_standing"), card.get("owner_standing")
    if es and es.get("caption") and es.get("score") is not None:
        add("standing", "Expert rating", es["caption"], source=es.get("source"))
    if os_ and os_.get("summary"):
        add("standing", "Owner rating", os_["summary"] + (f" - {os_['caption']}" if os_.get("caption") else ""),
            source=os_.get("source"), url=os_.get("source_url"))
    for r in card.get("reasons") or []:
        if r.get("evidence_class") == "spec" and "similar" in r.get("text", ""):
            add("score", "Compared with similar cars", r["text"], source="CarRec catalogue")
    for u in card.get("unknowns") or []:
        add("unknown_ncap" if "crash" in str(u).lower() else "unknown", "Not on record", "Unknown: " + str(u))

    # drop exact duplicates (same kind and text), keep the first; then cap
    seen_keys, unique = set(), []
    for it in items:
        k = (it["kind"], it["text"])
        if k not in seen_keys:
            seen_keys.add(k)
            unique.append(it)
    facts: List[Fact] = []
    for i, it in enumerate(unique[:MAX_FACTS], 1):
        toks = [(v, c) for v, c, _ in numeric_tokens(it["text"])]
        if it["kind"] == "price" and price is not None:
            toks.append((float(price), "money"))
        facts.append(Fact(id=f"f{i}", kind=it["kind"], label=it["label"], text=it["text"], source=it["source"],
                          url=it["url"], date=it["date"], tokens=toks))
    return facts


def facts_hash(facts: List[Fact]) -> str:
    blob = json.dumps([[f.id, f.kind, f.text, f.url] for f in facts], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]
