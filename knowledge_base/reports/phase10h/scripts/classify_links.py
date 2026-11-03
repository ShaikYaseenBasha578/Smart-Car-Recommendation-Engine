"""Phase 10H, read-only: classify every resolved aggregator observation (91wheels / v3cars / carwale) as a correct
link or a mislink, using the observation's structured fields first (fuel, gearbox, engine cc, price) and its name
only for the trim.

Usage: classify_links.py <db_copy> <out.tsv>
Per observation:
  parse  fuel, gearbox (auto/manual), cc, price, trim key, edition words  (structured field > slug > name)
  C      = variants of the same model compatible with fuel / gearbox / cc (when the source states them)
  E      = members of C whose trim key equals the observation's trim key (edition words must match too)
Classes:
  OK              resolved variant in E
  OK_COLOUR       E empty only because of a dual-tone/colour suffix the KB doesn't model; resolved is the base
  MISLINK_TARGET  resolved not in E, E non-empty (a better KB target exists; listed)
  EDITION_NOT_IN_KB  same trim, fuel and gearbox, but the source names an edition the KB doesn't have
  MISLINK_NONE    resolved contradicts fuel/gearbox/cc/trim and E is empty (the KB has no such variant)
  REVIEW          trim key could not be derived on one side (name too short / unparsed)
"""
import csv
import json
import re
import sqlite3
import sys

db = sqlite3.connect(sys.argv[1]); db.row_factory = sqlite3.Row

AUTO = {"at", "amt", "ags", "cvt", "ivt", "dct", "dca", "dsg", "tc", "automatic", "ecvt", "e-cvt", "auto"}
MANUAL = {"mt", "manual", "imt"}  # iMT is a clutchless manual; the KB stores it as 'iMT' (manual family)
CONFIG = AUTO | MANUAL | {
    "petrol", "diesel", "cng", "icng", "electric", "ev", "hybrid", "turbo", "tcmpfi", "mpfi", "tgdi", "gdi", "mpi", "crdi",
    "crde", "mhawk", "mstallion", "tsi", "tce", "kappa", "revotron", "revotorq", "smartstream", "b4d", "hra0", "k15c",
    "k12n", "m15d", "dualjet", "neodrive", "2wd", "4wd", "awd", "rwd", "fwd", "4x4", "4x2", "allgrip", "seater", "str",
    "speed", "litre", "kwh", "lr", "mr", "sr", "er", "d117", "d150", "d175", "g1", "g1.5", "cc", "bhp", "6mt", "5mt",
    "6at", "7dct", "normal"}
PHRASES = [r"smart hybrid", r"strong hybrid", r"mild hybrid", r"allgrip select", r"neo ?drive"]
SUBST = [(r"\bez[ -]?shift\b", " amt "), (r"\bstd\b", " standard "), (r"\b(hy|bi)[ -]?(fuel)?[ -]?cng\b", " cng "), (r"\bmid[ -]?range\b", " mr "),
         (r"\b(platinum white pearl|pearl arctic white|super white|attitude black|silver metallic)\b", " dt ")]
EDITION = {"dark", "camo", "knight", "black", "anniversary", "red", "jet", "matte", "kaziranga", "summer", "special", "edition"}
COLOUR = {"dt", "dual", "tone", "dualtone", "hard", "soft", "top", "mocha", "ivory"}  # paint / roof only


def fuel_of(text):
    t = text.lower()
    if "cng" in t: return "cng"
    if re.search(r"\b(ev|electric)\b|kwh", t): return "electric"
    if "diesel" in t or re.search(r"\bcrdi\b|\bmhawk\b|\bd1[157]\d\b", t): return "diesel"
    if "strong hybrid" in t or re.search(r"\bhybrid\b", t) and "smart hybrid" not in t and "mild" not in t: return "hybrid"
    if "petrol" in t: return "petrol"
    return None


def gearbox_of(text):
    toks = set(re.findall(r"[a-z0-9\-]+", text.lower().replace("(", " ").replace(")", " ")))
    a, m = bool(toks & AUTO) or "automatic" in text.lower(), bool(toks & MANUAL)
    return "auto" if a and not m else "manual" if m and not a else None


TATA_MODELS = {'Punch EV', 'Tiago EV', 'Nexon EV', 'Tiago', 'Harrier', 'Nexon', 'Tigor', 'Altroz'}
KB_FUEL = {"Petrol": "petrol", "Diesel": "diesel", "CNG": "cng", "Electric": "electric", "Petrol Hybrid": "hybrid",
           "Diesel Mild Hybrid": "diesel", "Flex Fuel": "petrol"}


def norm_tokens(s):
    s = s.lower().replace("+", " plus ")
    for ph in PHRASES:
        s = re.sub(ph, " petrol ", s)  # config phrases that would otherwise leave trim words ('smart', 'select')
    for a, b in SUBST:
        s = re.sub(a, b, s)
    s = re.sub(r"\(o\)|\bopt(ional)?\b|\(opt\)", " o ", s)
    s = re.sub(r"\(s\)", " s ", s)
    s = re.sub(r"\(ps\)", " ps_ ", s)  # Nexon 'PS' trim (panoramic sunroof) is identity, not power
    s = re.sub(r"\b\d+\s*-?\s*speed\b", " ", s)
    s = re.sub(r"(\d+)(\.\d+)?\s*kwh\b", r" kwh\1 ", s)  # battery: '30.0 kWh' / '30kWh' -> kwh30; '19.2kWh' -> kwh19
    s = re.sub(r"(\d\.\d)\s*l\b", r" \1 litre ", s)
    s = re.sub(r"\b(\d)\s*(seater|str)\b|\b(\d)(seater|str)\b", lambda m: f" seats{m.group(1) or m.group(3)} ", s)
    s = re.sub(r"[()\[\],/]", " ", s).replace("-", " ")
    return s.split()


def trim_key(name, model):
    """Identity tokens before the first config word; letters+digits glued ('hx 2' -> 'hx2')."""
    for m in (model, model.replace(" ", "")):
        name = re.sub(re.escape(m), " ", name, flags=re.I)
    model_words = {w.lower() for w in model.split()}
    toks, ed, col, seats, battery = [], set(), set(), None, None
    for t in norm_tokens(name):
        if t.startswith("seats"): seats = t[5:]; continue
        if re.fullmatch(r"kwh\d+", t): battery = t[3:]; continue
        if t in model_words: continue  # KB 'Classic S11' (model 'Scorpio Classic')
        if t in EDITION: ed.add(t); continue
        if t in COLOUR: col.add(t); continue
        if t in CONFIG or re.fullmatch(r"\d\.\d+|\d{3,4}|\d+ps", t):
            if toks: break
            continue  # leading config words (Magnite KB names start 'MT VISIA')
        toks.append(t)
    # compare as sorted letter/digit runs, so 'HX 2' == 'HX2', 'AX7 L' == 'AX7L', 'AC 5 Seater' order-free
    atoms = [a for t in toks for a in re.findall(r"[a-z]+|\d+", t.replace("ps_", "ps"))]
    key = Key(atoms)
    key.with_battery = Key(atoms + [battery]) if battery else None  # KB names carry the battery as a bare number ('Smart 30')
    return key, frozenset(ed - {"edition"}), bool(col), seats


class Key(tuple):
    """Trim identity: equal if the sorted letter/digit runs match or the in-order concatenation matches ('REV X A' == 'REVX A')."""
    def __new__(cls, atoms):
        k = super().__new__(cls, sorted(atoms)); k.flat = "".join(atoms); return k
    def __eq__(self, other): return tuple.__eq__(self, other) or self.flat == getattr(other, "flat", None)
    def __ne__(self, other): return not self.__eq__(other)
    __hash__ = tuple.__hash__


def parse_obs(src, raw_name, payload):
    try:
        p = json.loads(payload or "{}")
        if isinstance(p, str): p = json.loads(p)
    except Exception:
        p = {}
    fuel = gear = cc = price = None
    name = raw_name
    if src == "91wheels":
        r = p.get("raw", {}) if isinstance(p, dict) else {}
        slug = (r.get("v_variant_slug") or "").replace("-", " ")
        fuel = fuel_of(r.get("v_variant_fuel_type") or "") or fuel_of(raw_name) or fuel_of(slug)
        gear = gearbox_of(raw_name) or gearbox_of(slug)
        pr = r.get("v_variant_price") or (r.get("variant_price") or {}).get("ex_showroom_price")
        price = float(pr) if pr not in (None, "") else None
    elif src == "carwale":
        f = p.get("features", {}) if isinstance(p, dict) else {}
        name = (p.get("v_variant_name") or raw_name) if isinstance(p, dict) else raw_name
        fuel = fuel_of(f.get("Fuel Type") or "") or fuel_of(name)
        gear = gearbox_of(f.get("Transmission") or "") or gearbox_of(name)
        m = re.match(r"\s*(\d{3,4})\s*cc", f.get("Engine") or "")
        cc = float(m.group(1)) if m else None
        price = float(p["ex_showroom_price"]) if isinstance(p, dict) and p.get("ex_showroom_price") else None
    else:  # v3cars: glued "ModelTrim1.2L  Turbo Petrol Manual"
        fuel, gear = fuel_of(raw_name), gearbox_of(raw_name)
        m = re.search(r"([\d.]+)\s*Lakh", (p.get("ex_showroom_price") or "") if isinstance(p, dict) else "")
        price = float(m.group(1)) * 1e5 if m else None
    return dict(name=name, fuel=fuel, gear=gear, cc=cc, price=price)


variants = {}
for v in db.execute("""select v.id, v.model_id, m.name model, v.name, v.transmission, v.base_variant_id,
                       p.fuel_type, p.engine_cc, coalesce(v.price_ex_showroom, b.price_ex_showroom) price
                       from variant v join model m on m.id=v.model_id left join powertrain p on p.id=v.powertrain_id
                       left join variant b on b.id=v.base_variant_id"""):
    d = dict(v)
    d["fuel"] = KB_FUEL.get(d["fuel_type"])
    d["gear"] = "manual" if d["transmission"] in ("Manual", "iMT") else "auto"
    d["key"], d["ed"], _, d["seats"] = trim_key(d["name"], d["model"])
    variants[d["id"]] = d
by_model = {}
for d in variants.values(): by_model.setdefault(d["model_id"], []).append(d)


def compatible(v, o):
    return ((o["fuel"] is None or v["fuel"] is None or o["fuel"] == v["fuel"] or (o["fuel"] == "petrol" and v["fuel"] == "hybrid"))
            and (o["gear"] is None or o["gear"] == v["gear"])
            and (o["cc"] is None or v["engine_cc"] is None or abs(o["cc"] - v["engine_cc"]) <= 50))


rows = []
for r in db.execute("""select o.id, s.name src, o.raw_name, o.raw_payload, o.resolution_status st, o.resolved_variant_id vid
                       from source_observation o join source s on s.id=o.source_id
                       where s.name in ('91wheels','v3cars','carwale') and o.resolved_variant_id is not null order by o.id"""):
    rv = variants[r["vid"]]
    o = parse_obs(r["src"], r["raw_name"], r["raw_payload"])
    o["key"], o["ed"], colour, o["seats"] = trim_key(o["name"], rv["model"])
    def same_trim(v):
        if v["ed"] != o["ed"] or (o["seats"] and v["seats"] and o["seats"] != v["seats"]): return False
        if v["key"] == o["key"] or (o["key"].with_battery is not None and v["key"] == o["key"].with_battery): return True
        if o["gear"] != "auto" and v["gear"] != "auto":
            return False
        if v["model"] not in TATA_MODELS:  # Kia '(A)' means ADAS, not automatic
            return False
        # Tata: 'XTA' / 'XZA+' = XT / XZ+ automatic; a standalone 'A' ('Pure+ A', 'Fearless Plus A') means automatic too
        if len(v["key"]) == len(o["key"]) and all(a == b or a == b + "a" for a, b in zip(v["key"], o["key"])):
            return True
        vk, ok = list(v["key"]), list(o["key"])
        for k in (vk, ok):
            if "a" in k: k.remove("a")
        return vk == ok and len(vk) > 0 and (len(v["key"]) != len(o["key"]))
    C = [v for v in by_model[rv["model_id"]] if compatible(v, o)]
    E = [v for v in C if same_trim(v)]
    why = []
    if not compatible(rv, o):
        if o["fuel"] and rv["fuel"] and o["fuel"] != rv["fuel"] and not (o["fuel"] == "petrol" and rv["fuel"] == "hybrid"): why.append(f"fuel {o['fuel']}≠{rv['fuel']}")
        if o["gear"] and o["gear"] != rv["gear"]: why.append(f"gearbox {o['gear']}≠{rv['gear']}({rv['transmission']})")
        if o["cc"] and rv["engine_cc"] and abs(o["cc"] - rv["engine_cc"]) > 50: why.append(f"cc {o['cc']:.0f}≠{rv['engine_cc']:.0f}")
    if not same_trim(rv): why.append(f"trim '{o['key']}{'+' + ','.join(sorted(o['ed'])) if o['ed'] else ''}'≠'{rv['key']}{'+' + ','.join(sorted(rv['ed'])) if rv['ed'] else ''}'")
    if not o["key"] or not rv["key"]:
        cls = "REVIEW"
    elif rv in E:
        cls = "OK"
    elif E:
        cls = "MISLINK_TARGET"
    elif not why:
        cls = "OK"
    elif colour and compatible(rv, o) and same_trim(rv):
        cls = "OK_COLOUR"
    elif compatible(rv, o) and o["key"] == rv["key"] and o["ed"] > rv["ed"]:
        cls = "EDITION_NOT_IN_KB"  # an edition the KB doesn't model, attached to its base
    else:
        cls = "MISLINK_NONE"
    pd = (round((o["price"] - rv["price"]) / rv["price"] * 100, 1) if o["price"] and rv["price"] else None)
    if len(E) > 1 and rv not in E and cls == "MISLINK_TARGET" and o["seats"] is None and len({v["seats"] for v in E}) > 1:
        cls = "MISLINK_TARGET"  # several seat versions; still a mislink, target ambiguous
    rows.append(dict(obs=r["id"], src=r["src"], status=r["st"], cls=cls, model=rv["model"], raw=r["raw_name"].strip(),
                     payload_name=(o["name"].strip() if o["name"] != r["raw_name"] else ""),
                     resolved=r["vid"], resolved_name=rv["name"], why="; ".join(why), price_delta_pct=pd,
                     targets=",".join(f"{v['id']}:{v['name']}" for v in E[:4]) + ("…" if len(E) > 4 else ""),
                     o_fuel=o["fuel"], o_gear=o["gear"], o_cc=o["cc"], o_price=o["price"]))
with open(sys.argv[2], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t"); w.writeheader(); w.writerows(rows)
from collections import Counter
print(Counter(r["cls"] for r in rows))
print(Counter((r["src"], r["cls"]) for r in rows))
