"""Variant identity: does a source's name describe exactly this KB variant?

Identity = trim words + edition words + seats + battery, compared as sorted letter/digit runs so that spacing
doesn't matter ('HX 2' == 'HX2', 'AX7 L' == 'AX7L'). Fuel, gearbox and engine come from the source's structured
fields, then its slug, then its name; an attribute the source doesn't state is a wildcard, so several candidates
remain and the match goes to review instead of being guessed.

Naming facts (validated against the KB in Phase 10H): Tata 'XTA', 'XZA+', 'Pure+ A' are the automatic of that trim;
Kia '(A)' is an ADAS trim, not an automatic; Maruti 'Smart Hybrid' is a mild hybrid, stored as Petrol.
"""
import re
from collections import namedtuple

# Editions with an identity contradiction are held (policy P8): never an auto-accept target.
HELD_VARIANT_IDS = frozenset({815, 816, 821, 833})
TATA_MODELS = frozenset({"Altroz", "Harrier", "Nexon", "Nexon EV", "Punch EV", "Tiago", "Tiago EV", "Tigor"})

AUTO = {"at", "amt", "ags", "cvt", "ivt", "dct", "dca", "dsg", "tc", "automatic", "ecvt", "e-cvt", "auto"}
MANUAL = {"mt", "manual", "imt"}  # iMT is a clutchless manual, stored as 'iMT' (manual family)
CONFIG = AUTO | MANUAL | {
    "petrol", "diesel", "cng", "icng", "electric", "ev", "hybrid", "turbo", "tcmpfi", "mpfi", "tgdi", "gdi", "mpi", "crdi",
    "crde", "mhawk", "mstallion", "tsi", "tce", "kappa", "revotron", "revotorq", "revotroq", "smartstream", "b4d", "hra0", "k15c",
    "k12n", "m15d", "dualjet", "neodrive", "2wd", "4wd", "awd", "rwd", "fwd", "4x4", "4x2", "allgrip", "seater", "str",
    "speed", "litre", "kwh", "lr", "mr", "sr", "er", "d117", "d150", "d175", "g1", "g1.5", "cc", "bhp", "6mt", "5mt",
    "6at", "7at", "8at", "7dct", "normal", "vtec", "ivtec"}
PHRASES = [r"smart hybrid", r"strong hybrid", r"mild hybrid", r"allgrip select", r"neo ?drive", r"i-?vtec", r"t-gdi"]
SUBST = [(r"\bez[ -]?shift\b", " amt "), (r"\bstd\b", " standard "), (r"\b(hy|bi)[ -]?(fuel)?[ -]?cng\b", " cng "),
         (r"\bmid[ -]?range\b", " mr "),
         (r"\b(platinum white pearl|pearl arctic white|super white|attitude black|silver metallic)\b", " dt ")]
EDITION = {"dark", "camo", "knight", "black", "anniversary", "red", "jet", "matte", "kaziranga", "summer", "special",
           "edition", "adv", "signature", "stealth", "launch", "kuro", "vibe", "star"}
COLOUR = {"dt", "dual", "tone", "dualtone", "hard", "soft", "top", "mocha", "intrs", "ivory"}  # paint, roof, trim colour
KB_FUEL = {"petrol": "petrol", "diesel": "diesel", "cng": "cng", "electric": "electric", "petrol hybrid": "hybrid",
           "hybrid": "hybrid", "diesel mild hybrid": "diesel", "flex fuel": "petrol"}

Identity = namedtuple("Identity", "key flat battery editions dual_tone seats")
Attributes = namedtuple("Attributes", "fuel gear kind cc litres turbo drive dual_tone")


def fuel_of(text):
    t = (text or "").lower()
    if "cng" in t: return "cng"
    if re.search(r"\b(ev|electric)\b|kwh", t) and "electric + petrol" not in t: return "electric"
    if "diesel" in t or re.search(r"\bcrdi\b|\bcrde\b|\bmhawk\b|\brevotor?q\b|\bd1[157]\d\b", t): return "diesel"
    if "strong hybrid" in t or "electric + petrol" in t or re.search(r"\be-?cvt\b", t): return "hybrid"
    if re.search(r"\bhybrid\b", t) and "smart hybrid" not in t and "mild" not in t: return "hybrid"
    if re.search(r"petrol|smart hybrid|t-?gdi|\bgdi\b|\btsi\b|tcmpfi|\bmpfi\b|\bmpi\b|mstallion|revotron|i-?vtec|smartstream|kappa", t):
        return "petrol"
    return None


def gear_of(text):
    t = re.sub(r"[()]", " ", (text or "").lower())
    toks = set(re.findall(r"[a-z0-9\-]+", t))
    a = bool(toks & AUTO) or "automatic" in t or bool(re.search(r"\b\d(at|dct|dsg)\b", t))
    m = bool(toks & MANUAL)
    if a and m:  # 'AT (iMT)' and 'Clutchless Manual' name a clutchless manual
        return "manual" if "imt" in toks or "clutchless" in toks else None
    return "auto" if a else "manual" if m else None


def _tokens(s):
    s = s.lower().replace("+", " plus ")
    for ph in PHRASES:
        s = re.sub(ph, " petrol ", s)  # config phrases that would otherwise leave trim words ('smart', 'select')
    for a, b in SUBST:
        s = re.sub(a, b, s)
    s = re.sub(r"\(o\)|\bopt(ional)?\b|\(opt\)", " o ", s)
    s = re.sub(r"\(s\)", " s ", s)
    s = re.sub(r"\(ps\)", " ps_ ", s)  # Nexon 'PS' trim (panoramic sunroof) is identity, not power
    s = re.sub(r"\b\d+\s*-?\s*speed\b", " ", s)
    s = re.sub(r"(\d+)(\.\d+)?\s*kwh\b", r" kwh\1 ", s)  # '30.0 kWh', '30kWh' -> kwh30; '19.2kWh' -> kwh19
    s = re.sub(r"(\d\.\d)\s*l\b", r" \1 litre ", s)
    s = re.sub(r"\b(\d)\s*(seater|str)\b|\b(\d)(seater|str)\b", lambda m: f" seats{m.group(1) or m.group(3)} ", s)
    s = re.sub(r"[()\[\],/]", " ", s).replace("-", " ")
    return s.split()


def identity_of(name, model):
    """Parse a variant name. Trim words stop at the first config word; edition, colour and seat words count anywhere."""
    for m in (model, model.replace(" ", "")):
        name = re.sub(re.escape(m), " ", name or "", flags=re.I)
    model_words = {w.lower() for w in model.split()}
    toks, eds, dual, seats, battery, ended = [], set(), False, None, None, False
    for t in _tokens(name):
        if t.startswith("seats"): seats = t[5:]; continue
        if re.fullmatch(r"kwh\d+", t): battery = t[3:]; continue
        if t in model_words: continue  # KB 'Classic S11' (model 'Scorpio Classic')
        if t in EDITION: eds.add(t); continue
        if t in COLOUR:
            if t in ("dt", "dual", "tone", "dualtone"): dual = True
            continue
        if ended: continue
        if t in CONFIG or re.fullmatch(r"\d\.\d+|\d{3,4}|\d+ps", t):
            ended = bool(toks)  # leading config words don't end the trim (Magnite KB names start 'MT VISIA')
            continue
        toks.append(t)
    atoms = [a for t in toks for a in re.findall(r"[a-z]+|\d+", t.replace("ps_", "ps"))]
    return Identity(tuple(sorted(atoms)), "".join(atoms), battery, frozenset(eds - {"edition"}), dual, seats)


def attributes_of(name, slug=None, fuel=None, trans=None, cc=None, engine_name=None):
    """Structured field, then slug, then name. Anything not stated stays None (a wildcard)."""
    slug_text = (slug or "").replace("-", " ")
    text = f"{name or ''} {engine_name or ''}"
    f = KB_FUEL.get((fuel or "").strip().lower()) or fuel_of(fuel) or fuel_of(text) or fuel_of(slug_text)
    g = gear_of(trans) or gear_of(name) or gear_of(slug_text)
    t = text.lower()
    m = re.search(r"(?<![\d.])(\d\.\d)\s*(?:l\b|litre|tsi|tgdi|t-gdi|turbo|mpi|crdi|d\b)", t) or re.search(r"\bg?(\d\.\d)\b", t)
    litres = float(m.group(1)) if m else None
    turbo = True if re.search(r"turbo|t-?gdi|\btsi\b|tcmpfi", t) else False if re.search(r"\bmpi\b|\bmpfi\b", t) else None
    kind = kind_of(trans) or kind_of(name) or kind_of(slug_text)
    drive = "two" if re.search(r"\b(2wd|4x2|fwd|rwd)\b", t) else "four" if re.search(r"\b(4wd|4x4|awd|allgrip)\b", t) else None
    dual = bool(re.search(r"\bdt\b|dual[ -]?tone", t))
    return Attributes(f, g, kind, float(cc) if cc else None, litres, turbo, drive, dual)


def kind_of(text):
    """The specific automatic, when stated: 'amt', 'cvt' (CVT/IVT), 'dct' (DCT/DSG/DCA) or 'tc'. None for a bare 'AT'."""
    t = re.sub(r"[()]", " ", (text or "").lower())
    if re.search(r"\bamt\b|\bags\b|ez[ -]?shift|autoshift", t): return "amt"
    if re.search(r"\be-?cvt\b|\bcvt\b|\bivt\b", t): return "cvt"
    if re.search(r"\bdct\b|\bdsg\b|\bdca\b", t): return "dct"
    if re.search(r"\btc\b|torque converter", t): return "tc"
    return None


def kb_gear(transmission):
    return "manual" if (transmission or "").lower() in ("manual", "imt", "mt") else "auto"


def compatible(row, a):
    """Hard filter on every attribute the source states. `row` needs fuel_type, transmission, engine_cc, drivetrain."""
    kf = KB_FUEL.get((row["fuel_type"] or "").lower())
    if a.fuel and kf and a.fuel != kf and not (a.fuel == "petrol" and kf == "hybrid"): return False
    if a.gear and row["transmission"] and a.gear != kb_gear(row["transmission"]): return False
    if a.kind and kind_of(row["transmission"]) not in (None, a.kind): return False
    cc = row["engine_cc"]
    if a.cc and cc and abs(a.cc - cc) > 50: return False
    if a.litres and cc and not a.cc and abs(cc / 1000 - a.litres) > 0.06: return False
    drivetrain = row["drivetrain"] if "drivetrain" in row.keys() else None
    if a.drive and drivetrain and (drivetrain.upper() in ("FWD", "RWD", "2WD")) != (a.drive == "two"): return False
    return True


def same_identity(kb, src, model, auto_stated):
    """kb and src are Identity tuples. `auto_stated`: the source or the candidate is an automatic (Tata 'A' rule)."""
    if kb.editions != src.editions: return False
    if src.seats and kb.seats and src.seats != kb.seats: return False
    if kb.key == src.key or kb.flat == src.flat: return True
    if src.battery and kb.key == tuple(sorted(src.key + (src.battery,))): return True
    if model not in TATA_MODELS or not auto_stated: return False  # Kia '(A)' means ADAS, so this is Tata only
    if len(kb.key) == len(src.key) and all(x == y or x == y + "a" for x, y in zip(kb.key, src.key)): return True
    k, s = list(kb.key), list(src.key)
    for lst in (k, s):
        if "a" in lst: lst.remove("a")
    return k == s and bool(k) and len(kb.key) != len(src.key)


def narrow(candidates, a):
    """Tie-breakers among identity matches; each one only removes candidates, and never all of them."""
    def keep(cs, pred):
        sub = [c for c in cs if pred(c)]
        return sub or cs
    cs = list(candidates)
    is_turbo = lambda c: bool(re.search(r"turbo|tsi|tgdi|tce", c["name"].lower()))
    if a.turbo is True: cs = keep(cs, is_turbo)
    # A stated non-turbo engine is a hard filter: the turbo variant is a different car.
    if a.turbo is False: cs = [c for c in cs if not is_turbo(c)]
    return cs


def apply_dual_tone(cs, a):
    """Owner decision 2: the source says dual tone -> the DT variant if one exists; the source is silent -> the base.
    A silent source with only DT candidates has no base to link to, so nothing is left (review)."""
    is_dt = lambda c: bool(re.search(r"dual[ -]?tone", c["name"].lower()))
    # Dual tone must not settle a gearbox or fuel the source didn't state.
    if (a.gear is None and len({kb_gear(c["transmission"]) for c in cs}) > 1) or (a.fuel is None and len({c["fuel_type"] for c in cs}) > 1):
        return cs
    if a.dual_tone:
        return [c for c in cs if is_dt(c)] or cs
    return [c for c in cs if not is_dt(c)]
