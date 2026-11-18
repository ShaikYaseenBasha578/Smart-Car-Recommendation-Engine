"""Shared value parsers for aggregator payloads. Absent or blank is None (unknown), never 0."""
import re

_NO = {"no", "not available", "na", "n/a", "none", "0", "false"}


def num(s):
    if s is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(s).replace(",", ""))
    return float(m.group(0)) if m else None


def yes_no(s):
    """1 when the source states the feature, 0 when it states its absence, None when blank."""
    if s is None:
        return None
    t = re.sub(r"\s+", " ", str(s)).strip().lower()
    if t == "":
        return None
    return 0 if t in _NO else 1


def fuel(s, name=""):
    t = (str(s or "") + " ").lower()
    n = " " + (name or "").lower() + " "
    if "cng" in t:
        return "CNG"
    if "mild" in t and "diesel" in t:
        return "Diesel Mild Hybrid"
    if "mild" in t:
        return "Petrol"
    if "hybrid" in t or "electric + petrol" in t or "petrol + electric" in t:
        return "Petrol Hybrid"
    if "electric" in t:
        return "Electric"
    if "diesel" in t:
        return "Diesel"
    if "flex" in t:
        return "Flex Fuel"
    if "petrol" in t:
        # a site may write plain "Petrol" for a strong hybrid and say "Hybrid" only in the variant name
        if " hybrid " in re.sub(r"[^a-z]+", " ", n) + " " and not re.search(r"\b(mild|smart)\b", n):
            return "Petrol Hybrid"
        return "Petrol"
    return None


def transmission(s, name="", fuel_type=None):
    """KB vocabulary from a source's transmission text plus the variant name. None when it cannot be told."""
    t = " " + re.sub(r"[()\-/]", " ", (str(s or "") + " " + (name or "")).lower()) + " "
    if "e cvt" in t or "ecvt" in t:
        return "e-CVT"
    if " amt " in t or " ags " in t or "automated manual" in t:
        return "AMT"
    if " cvt " in t or " ivt " in t:
        return "CVT"
    if " dct " in t or " dsg " in t or " dca " in t or "dual clutch" in t:
        return "DCT"
    if " tc " in t or "torque converter" in t:
        return "Torque Converter"
    if " imt " in t or "clutchless" in t:
        return "iMT"
    if fuel_type == "Electric":
        return "Automatic"
    if "automatic" in t or " at " in t:
        return "Automatic"
    if "manual" in t or " mt " in t:
        return "Manual"
    return None


def trans_class(kb_transmission):
    if kb_transmission is None:
        return None
    return "M" if kb_transmission in ("Manual", "iMT") else "A"


_STOP = {"petrol", "diesel", "cng", "electric", "hybrid", "manual", "automatic", "mt", "at", "amt", "cvt", "dct", "ivt",
         "imt", "tc", "ags", "dsg", "dca", "speed", "turbo", "str", "seater", "kwh", "the", "icng", "ev",
         "clutchless", "edition", "suzuki", "maruti", "smart", "mild", "strong"}


def trim_tokens(name, model=""):
    """Identity tokens of a variant name: what is left after fuel, gearbox and engine words are removed.
    Spelling differences between sites that do not change identity are folded: "HX2"/"HX 2", "(O)"/"Opt",
    "DT"/"Dual Tone", "7 STR"/"7Str", "59.0 kWh"/"59kWh", the default two-wheel drive ("2WD", "RWD", "4X2": dropped),
    four-wheel drive ("4WD", "4X4", "AWD", "QWD": one token), and a bundled AC charger ("7.2kW Charger", "ACFC")."""
    t = (name or "").lower()
    t = re.sub(r"\(\s*electric\s*\+\s*(petrol|diesel)\s*\)", " ", t)
    t = t.replace("+", " plus ").replace("(o)", " o ").replace("(s)", " s ")
    t = re.sub(r"\be[\s-]?cvt\b", " ", t)
    t = re.sub(r"\b\d(\.\d)?\s*-?\s*lit(re|er)\b", " ", t)
    t = re.sub(r"\bno charger\b", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*kw\s*(ac\s*)?(fast\s*)?charger\b|\bacfc\b|\bac fast charger\b", " acfc ", t)
    t = re.sub(r"\b(\d+)(\.\d+)?\s*kwh\b", lambda m: " %s%s " % (m.group(1), "" if m.group(2) in (None, ".0") else m.group(2).replace(".", "p")), t)
    t = re.sub(r"\b(2wd|rwd|fwd|4\s*x\s*2)\b", " ", t)
    t = re.sub(r"\b(4wd|awd|qwd|4\s*x\s*4)\b", " fourwd ", t)
    t = re.sub(r"\b\d\.\d\s*l?\b", " ", t)
    t = re.sub(r"\b\d\s*speed\b", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\b(\d)\s*(str|seater)\b", r"\1", t)
    t = re.sub(r"([a-z])(\d)", r"\1 \2", t)          # "HX2" and "HX 2" are the same words
    t = re.sub(r"(\d)([a-z])", r"\1 \2", t)
    t = re.sub(r"\bdt\b", "dual tone", t)
    t = re.sub(r"\bopt\b|\boptional\b", "o", t)
    mw = re.sub(r"[^a-z0-9]+", " ", (model or "").lower())
    mw = re.sub(r"(\d)([a-z])", r"\1 \2", re.sub(r"([a-z])(\d)", r"\1 \2", mw))
    drop = set(_STOP) | set(mw.split())
    return frozenset(w for w in t.split() if w not in drop)


def common_prefix(names):
    """Leading words shared by every name in a list (a site's own spelling of make and model), as a string."""
    rows = [n.split() for n in names if n]
    if len(rows) < 2:
        return ""
    out = []
    for words in zip(*rows):
        if len({w.lower() for w in words}) != 1:
            break
        out.append(words[0])
    return " ".join(out)


def norm_name(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower().replace("+", " plus ")).strip()


def seat_only(tokens):
    """True when every token is a bare seat count (one site writes '7 STR', the other leaves the default out)."""
    return all(re.match(r"^\d$", t) for t in tokens)


# ---------------------------------------------------------------- attributes compared on their own (missing-models rules)
_KWH = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*-?\s*kwh\b", re.I)
BATTERY_TOL = 0.05


def battery_kwh(*texts):
    """Battery capacity in kWh from the first text that states one ("42 kWh", "42.0 kWh", "42kWh", "51.4 kWh"), else None.
    A figure outside 5..250 kWh is not read (a page may print "345 kWh" for 34.5; that case is handled by page_battery_fix)."""
    for t in texts:
        m = _KWH.search(t or "")
        if m:
            x = float(m.group(1))
            if 5 <= x <= 250:
                return x
    return None


def battery_agrees(a, b):
    """True when both capacities are known and within 0.05 kWh (17.3 and 17.4 are different batteries)."""
    return a is not None and b is not None and abs(a - b) <= BATTERY_TOL + 1e-9


def page_battery_fix(page_norm, kwh):
    """Page-name check only. `page_norm` is norm_name() of a variant page's name. A page may drop the decimal point
    ("EC Pro 345 kWh" for 34.5 kWh); when the model-page name or sub-line says `kwh` (34.5), read "345 kWh" as 34.5 kWh."""
    if kwh is None or float(kwh) == int(kwh):
        return page_norm
    txt = "%g" % kwh
    return re.sub(r"\b%s kwh\b" % txt.replace(".", ""), "%s kwh" % txt.replace(".", " "), page_norm)


# Words that are already compared as attributes (fuel, gearbox, drive, engine, seats) and may be written in one site's
# name only. trim_tokens() already drops: petrol diesel cng electric hybrid mild strong manual automatic mt at amt cvt
# e-cvt dct ivt turbo str seater, "(Electric + Petrol/Diesel)", 2WD/RWD/4x2 (nothing) and 4WD/AWD/4x4 (one token), and
# "7 STR"/"7Str"/"7 Seater" (one seat token). The words below are the ones it did not drop; this is the complete list.
_DESCRIPTORS = (
    (re.compile(r"\bplug[\s-]*in\b"), " "),                 # "Plug-in Hybrid (Electric + Petrol)": the hybrid words go with it
    (re.compile(r"\be\s*:\s*hev\b|\behev\b"), " "),         # Honda's strong-hybrid badge, e:HEV
    (re.compile(r"\bwith\s+no\s+charger\b"), " "),        # "AX5 39.4 kWh with No Charger": trim_tokens drops "no charger" but not the "with"
)
_KWH_ANY = re.compile(r"\b\d+(?:\.\d+)?\s*-?\s*kwh\b")


def relaxed_tokens(name, model=""):
    """trim_tokens() with the battery size removed (compared as its own attribute) and the descriptor words above removed."""
    t = (name or "").lower()
    t = _KWH_ANY.sub(" ", t)
    for rx, sub in _DESCRIPTORS:
        t = rx.sub(sub, t)
    return trim_tokens(t, model)


DUAL_TONE = frozenset({"dual", "tone"})


def fuel_words(*texts):
    """Fuel and hybrid-kind words a text states, for the strong-hybrid contradiction check."""
    t = " " + re.sub(r"[^a-z]+", " ", " ".join(x or "" for x in texts).lower()) + " "
    return {w for w in ("diesel", "cng", "electric", "flex", "lpg", "mild", "smart") if " %s " % w in t}


def has_descriptor(name):
    """True when `name` carries one of the descriptor words removed by relaxed_tokens (so the link used rule 3)."""
    t = (name or "").lower()
    return any(rx.search(t) for rx, _ in _DESCRIPTORS)


def battery_values(text):
    """Every kWh figure printed in a text (a brochure line may name several packs)."""
    return [float(m.group(1)) for m in _KWH.finditer(text or "") if 5 <= float(m.group(1)) <= 250]
