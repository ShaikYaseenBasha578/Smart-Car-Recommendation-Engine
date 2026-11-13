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
