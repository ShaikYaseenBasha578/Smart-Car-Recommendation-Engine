"""Variant linking. Deliberately strict: a link is made only when identity is equal, never when it merely overlaps
(the 2026-09 resolver accepted overlaps and mislinked 558 observations).

Identity = fuel + gearbox class (manual / automatic) + the set of trim words left after fuel, gearbox and engine
words are removed. When several candidates share an identity (e.g. turbo and non-turbo), an exact ex-showroom price
match must pick exactly one, otherwise nothing is linked."""
from .sources import common as c

LINKER_VERSION = "2"     # bump when a linking rule changes: a model last processed under another version is processed again (extract.model_bundle)


def identity(name, model, fuel, trans):
    return (fuel, c.trans_class(trans), c.trim_tokens(name, model))


def _strict_link(target, candidates, model, need_price=False, price_tol=0.0):
    """The original linker, unchanged. Returns (candidate or None, reason)."""
    tid = identity(target["name"], model, target.get("fuel"), target.get("transmission"))
    if tid[0] is None or tid[1] is None:
        return None, "target fuel or gearbox unknown"
    exact = [x for x in candidates if c.norm_name(x["name"]) == c.norm_name(target["name"])]
    if len(exact) == 1 and not need_price:
        x = exact[0]
        if x.get("fuel") in (None, tid[0]) and c.trans_class(x.get("transmission")) in (None, tid[1]):
            return x, "exact name"
    pool = [x for x in candidates if identity(x["name"], model, x.get("fuel"), x.get("transmission")) == tid]
    if target.get("engine_cc") and any(x.get("engine_cc") for x in pool):
        pool = [x for x in pool if not x.get("engine_cc") or abs(x["engine_cc"] - target["engine_cc"]) <= 2]
    if not pool:
        # one site may leave out the default seat count; then fuel, gearbox class, the other trim words AND the exact
        # price must all agree, and only one candidate may qualify
        near = [x for x in candidates if x.get("fuel") == tid[0] and c.trans_class(x.get("transmission")) == tid[1]
                and (c.trim_tokens(x["name"], model) ^ tid[2]) and c.seat_only(c.trim_tokens(x["name"], model) ^ tid[2])
                and target.get("price") and x.get("price") and abs(x["price"] - target["price"]) <= price_tol * target["price"]]
        if len(near) == 1:
            return near[0], "identity (seat count implied) + price"
        return None, "no candidate with the same identity"

    def price_ok(x):
        if not target.get("price") or not x.get("price"):
            return False
        return abs(x["price"] - target["price"]) <= price_tol * target["price"]

    if len(pool) == 1 and (not need_price or price_ok(pool[0])):
        return pool[0], "identity"
    priced = [x for x in pool if price_ok(x)]
    if len(priced) == 1:
        return priced[0], "identity + price"
    return None, "%d candidates share the identity%s" % (len(pool), "" if not need_price else " or price differs")


# ---------------------------------------------------------------------------------------------------------------
# Missing-models rules (owner-approved 2026-11-18, PLAN_ADD_MISSING_MODELS.md). They apply only when link() is called
# with tier >= 1, which only the two-site linker (extract.py) does, and only to a target that the original linker above
# could not link. So a link that exists today cannot change. Every rule is exact and enumerated; nothing is fuzzy.
#   tier 1: R1 battery capacity compared as an attribute (both sides' kWh must agree within 0.05)
#           R2 strong-hybrid fuel (CarDekho "Petrol" = CarWale "Petrol Hybrid", only when `strong_hybrid` is passed)
#           R3 descriptor words (common.relaxed_tokens: "Plug-in", "e:HEV", on top of what trim_tokens already folds)
#           R4 (D1) a unique identity match whose price differs beyond tolerance -> "identity (price differs)"
#   tier 2: R3b "Dual Tone" written on one site only: links only with an agreeing price and one candidate
RULES = {"R1": "battery", "R2": "strong-hybrid fuel", "R3": "descriptor words", "R4": "price differs", "R3b": "dual tone on one site"}


def _rel(target, x, model, strong_hybrid, dual=False):
    """(ok, [rules used]) for one candidate under the tier-1 identity. dual=True also ignores a one-sided "dual tone"."""
    rules = []
    tf, xf = target.get("fuel"), x.get("fuel")
    if xf != tf:
        if not (strong_hybrid and tf == "Petrol Hybrid" and xf == "Petrol" and not c.fuel_words(x.get("name"), x.get("sub"))):
            return False, []
        rules.append("R2")
    tt = c.trans_class(target.get("transmission"))
    if tt is None or c.trans_class(x.get("transmission")) != tt:
        return False, []
    a, b = c.relaxed_tokens(target["name"], model), c.relaxed_tokens(x["name"], model)
    if dual:
        if a == b or (a - c.DUAL_TONE) != (b - c.DUAL_TONE) or (a & c.DUAL_TONE) == (b & c.DUAL_TONE):
            return False, []
        rules.append("R3b")
    elif a != b:
        return False, []
    bt = target.get("battery_kwh") or c.battery_kwh(target["name"])
    bx = x.get("battery_kwh") or c.battery_kwh(x["name"])
    if bt is not None and bx is not None:
        if not c.battery_agrees(bt, bx):
            return False, []
        rules.append("R1")
    if c.has_descriptor(target["name"]) or c.has_descriptor(x["name"]):
        rules.append("R3")
    return True, rules


def _relaxed_link(target, candidates, model, need_price, price_tol, tier, peers, strong_hybrid):
    if target.get("fuel") is None or c.trans_class(target.get("transmission")) is None:
        return None, "target fuel or gearbox unknown"

    def price_ok(x):
        return bool(target.get("price") and x.get("price")) and abs(x["price"] - target["price"]) <= price_tol * target["price"]

    def tag(rules):
        return "[%s]" % ", ".join(RULES[r] for r in rules) if rules else ""

    def pool_for(dual):
        out = [(x, r) for x in candidates for ok, r in [_rel(target, x, model, strong_hybrid, dual)] if ok]
        if target.get("engine_cc") and any(x.get("engine_cc") for x, _ in out):
            out = [(x, r) for x, r in out if not x.get("engine_cc") or abs(x["engine_cc"] - target["engine_cc"]) <= 2]
        return out

    pool = pool_for(False)
    if pool:
        if not need_price and len(pool) == 1:
            return pool[0][0], ("identity %s" % tag(pool[0][1])).strip()
        priced = [(x, r) for x, r in pool if price_ok(x)]
        if len(priced) == 1:
            x, r = priced[0]
            return x, ("%s %s" % ("identity" if len(pool) == 1 else "identity + price", tag(r))).strip()
        if len(pool) == 1 and need_price and target.get("price") and pool[0][0].get("price"):
            x, r = pool[0]
            # R4 (D1): both prices are known and differ beyond tolerance; the identity must also be unique among CarWale's versions
            if any(p is not target and _rel(p, x, model, strong_hybrid)[0] for p in (peers or [])):
                return None, "identity matches but another CarWale version shares it"
            return x, ("identity (price differs) %s" % tag(r)).strip()
        return None, "%d candidates share the identity or price differs" % len(pool)
    if tier >= 2:
        priced = [(x, r) for x, r in pool_for(True) if price_ok(x)]
        if len(priced) == 1:
            return priced[0][0], ("identity + price %s" % tag(priced[0][1])).strip()
    return None, "no candidate with the same identity"


def link(target, candidates, model, need_price=False, price_tol=0.0, tier=0, peers=None, strong_hybrid=False):
    """target/candidates: dicts with name, fuel, transmission, price (any may be None), and optional engine_cc, battery_kwh, sub.
    Returns (candidate or None, reason). tier 0 = the original linker. tier >= 1 first runs it, and only when it finds nothing
    applies the missing-models rules above. `peers` = every CarWale target of the model (R4 needs the identity to be unique among
    them); `strong_hybrid` = every current CarWale version of the model is a strong hybrid (R2)."""
    hit, why = _strict_link(target, candidates, model, need_price, price_tol)
    if hit is not None or tier == 0:
        return hit, why
    hit2, why2 = _relaxed_link(target, candidates, model, need_price, price_tol, tier, peers, strong_hybrid)
    return (hit2, why2) if hit2 is not None else (None, why)
