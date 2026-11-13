"""Variant linking. Deliberately strict: a link is made only when identity is equal, never when it merely overlaps
(the 2026-09 resolver accepted overlaps and mislinked 558 observations).

Identity = fuel + gearbox class (manual / automatic) + the set of trim words left after fuel, gearbox and engine
words are removed. When several candidates share an identity (e.g. turbo and non-turbo), an exact ex-showroom price
match must pick exactly one, otherwise nothing is linked."""
from .sources import common as c


def identity(name, model, fuel, trans):
    return (fuel, c.trans_class(trans), c.trim_tokens(name, model))


def link(target, candidates, model, need_price=False, price_tol=0.0):
    """target/candidates: dicts with name, fuel, transmission, price (any may be None), and optional engine_cc.
    Returns (candidate or None, reason)."""
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
