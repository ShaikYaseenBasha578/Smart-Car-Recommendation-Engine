"""Step 1 of PLAN_ADD_MISSING_MODELS.md: for every current CarWale version of the NEW_MODEL items in a discovery file, the best CarDekho
candidate on the same model page and the reason the ORIGINAL linker (tier 0) refuses it. Read-only, offline (cached pages only).
usage: python -m kbpipe.tools.missing_models_diagnostic <discovery.json> <out.md> [out.json]"""
import json
import re
import sys

from .. import config, fetch, match
from ..sources import cardekho as cd
from ..sources import carwale as cw
from ..sources import common as c

ORDER = ["A", "B", "C", "D", "E", "F"]
NAMES = {"A": "battery size in one name only", "B": "page-name kWh spelling", "C": "hybrid labelled Petrol",
         "D": "descriptor words", "E": "price beyond tolerance", "F": "genuinely different names"}


def cd_variants(m2):
    out = []
    for v in [v for v in (m2 or {}).get("variants", []) if v["status"] == "CURRENT"]:
        fuel = v["fuel"]
        if fuel == "Petrol" and "hybrid" in v["name"].lower() and not any(w in v["name"].lower() for w in ("mild", "smart")):
            fuel = "Petrol Hybrid"
        out.append({"name": v["name"], "fuel": fuel, "transmission": c.transmission(v["sub"], v["name"], fuel), "price": v["price"],
                    "engine_cc": c.num(v["sub"]) if "cc" in v["sub"] else None, "url": v["url"], "sub": v["sub"],
                    "battery_kwh": c.battery_kwh(v["name"], v["sub"])})
    return out


def best(t, cands, model):
    """Closest candidate: most shared trim words (after kWh, descriptor and dual-tone words are set aside), then price."""
    a = c.relaxed_tokens(t["name"], model) - c.DUAL_TONE

    def key(x):
        b = c.relaxed_tokens(x["name"], model) - c.DUAL_TONE
        j = len(a & b) / float(len(a | b) or 1)
        gap = abs((x["price"] or 0) - (t["price"] or 0))
        bt, bx = t.get("battery_kwh"), x.get("battery_kwh")
        return (j, c.battery_agrees(bt, bx) if bt and bx else False, -gap)
    return max(cands, key=key) if cands else None


def _kwh_token(name):
    """The token trim_tokens() makes of a kWh figure in a name ("42.0 kWh" -> "42", "17.3 kWh" -> "17p3"), or None."""
    m = re.search(r"\b(\d+)(\.\d+)?\s*kwh\b", (name or "").lower())
    return None if not m else "%s%s" % (m.group(1), "" if m.group(2) in (None, ".0") else m.group(2).replace(".", "p"))


def _no_kwh(name):
    return re.sub(r"\b\d+(?:\.\d+)?\s*-?\s*kwh\b", " ", (name or "").lower())


def classify(t, x, model, fetcher, tol, strong, cands):
    blocks, notes = [], []
    if x is None:
        return ["F"], ["no CarDekho variant"]
    sa, sb = c.trim_tokens(t["name"], model), c.trim_tokens(x["name"], model)
    ra, rb = c.relaxed_tokens(t["name"], model), c.relaxed_tokens(x["name"], model)
    same_price = [y for y in cands if y is not x and t["price"] and y["price"] and abs(y["price"] - t["price"]) <= tol * t["price"]]
    if same_price and not (x["price"] and t["price"] and abs(x["price"] - t["price"]) <= tol * t["price"]):
        notes.append("same price on CarDekho: %s" % "; ".join(y["name"] for y in same_price))
    if t["fuel"] != x["fuel"]:
        blocks.append("C")
        notes.append("fuel %s vs %s%s" % (t["fuel"], x["fuel"], "" if strong else " (not every CarWale version is a strong hybrid)"))
    bt, bx = t.get("battery_kwh"), x.get("battery_kwh")
    if bt and bx and not c.battery_agrees(bt, bx):
        blocks.append("F")
        notes.append("battery %g vs %g kWh" % (bt, bx))
    kw_a, kw_b = c.trim_tokens(_no_kwh(t["name"]), model), c.trim_tokens(_no_kwh(x["name"]), model)
    if not (bt and bx and not c.battery_agrees(bt, bx)) and sa != sb and kw_a == kw_b and (bt or bx):
        blocks.append("A")
        notes.append("kWh %s is in %s name only" % ("%g" % (bt or bx), "the CarWale" if bt and not _kwh_token(x["name"]) else ("the CarDekho" if bx and not _kwh_token(t["name"]) else "the CarWale and CarDekho (different spelling)")))
    if kw_a != ra or kw_b != rb:                 # descriptor words (plug-in, e:HEV, "with No Charger") are in the way
        blocks.append("D")
        notes.append("descriptor words: %s" % ", ".join(sorted((kw_a ^ ra) | (kw_b ^ rb))))
    diff = ra ^ rb
    if diff and not (diff - c.DUAL_TONE):
        blocks.append("D")
        notes.append("dual tone on one site")
    elif diff:
        blocks.append("F")
        notes.append("different words: %s" % ", ".join(sorted(diff)))
    if t["price"] and x["price"] and abs(t["price"] - x["price"]) > tol * t["price"]:
        blocks.append("E")
        notes.append("price %s vs %s" % (t["price"], x["price"]))
    # B: the old linker links, but the variant page's own name is spelled differently
    hit, why = match.link(t, [x], model, need_price=True, price_tol=tol)
    if hit is not None:
        p, _ = fetcher.get(x["url"])
        pv = cd.parse_variant(p) if p else None
        if pv:
            pn = " ".join(w for w in c.norm_name(pv["name"]).split() if w != "suzuki")
            ln = " ".join(w for w in c.norm_name(x["name"]).split() if w != "suzuki")
            if pn != ln:
                blocks.append("B")
                notes.append("page says %r, list says %r" % (pv["name"], x["name"]))
        elif p is None:
            notes.append("variant page not cached")
    return [b for b in ORDER if b in blocks], notes


def main(disc, out_md, out_json=None):
    cfg = config.load()
    f = fetch.Fetcher(cfg, log=lambda *a: None, offline=True)
    tol = cfg.get("link_price_tolerance", 0.005)
    d = json.load(open(disc))
    rows, per_model = [], []
    for it in [x for x in d if x.get("kind") == "NEW_MODEL"]:
        p, _ = f.get(it["cw"]["url"])
        m = cw.parse_model(p) if p else None
        p2, _ = f.get(it["cd"]["url"])
        m2 = cd.parse_model(p2) if p2 else None
        cdv = cd_variants(m2)
        site_model = c.common_prefix([v["name"] for v in cdv]) or (it["cd"].get("name") or "")
        model = " ".join([it["make"], it["model"], site_model])
        cur = [v for v in m["versions"] if v["status"] == "current"]
        strong = bool(cur) and all(v["fields"].get("fuel_type") == "Petrol Hybrid" for v in cur)
        per_model.append((it["make"], it["model"], len(cur), len(cdv)))
        for v in cur:
            fl = v["fields"]
            t = {"name": v["name"], "fuel": fl.get("fuel_type"), "transmission": fl.get("transmission"),
                 "price": fl.get("price_ex_showroom"), "engine_cc": fl.get("engine_cc"), "battery_kwh": c.battery_kwh(v["name"])}
            x = best(t, cdv, model)
            hit, why = match.link(t, cdv, model, need_price=True, price_tol=tol)
            blocks, notes = classify(t, x, model, f, tol, strong, cdv)
            if not blocks and hit is None:
                blocks = ["other"]
            rows.append({"make": it["make"], "model": it["model"], "carwale": v["name"], "special": v["special"], "cw_fuel": t["fuel"],
                         "cw_price": t["price"], "cd": x["name"] if x else "", "cd_fuel": x["fuel"] if x else "",
                         "cd_price": x["price"] if x else None, "old_linker": "links" if hit else why, "blocks": blocks, "notes": "; ".join(notes)})
    tot_any = {b: sum(1 for r in rows if b in r["blocks"]) for b in ORDER + ["other"]}
    prim = {}
    for r in rows:
        k = next((b for b in ("F", "B", "A", "C", "D", "E", "other") if b in r["blocks"]), "none")
        prim[k] = prim.get(k, 0) + 1
    L = ["# Missing models: diagnostic of why nothing links (step 1, no code change)", "",
         "Source: cached CarWale and CarDekho model pages from the 17 Nov discovery file (`%s`), original linker (tier 0 = the linker before any change). "
         "Offline: no page was fetched for this report." % disc, "",
         "Per CarWale version: the best CarDekho candidate on the model page (most shared trim words once battery, descriptor and dual-tone words are set aside, "
         "then nearest price) and the blocks that stop the link. A version can have several blocks. Blocks: " +
         "; ".join("**%s** %s" % (b, NAMES[b]) for b in ORDER) + ". `other` = none of these explains it.", "",
         "## Totals", "", "CarWale versions examined: **%d** across %d models." % (len(rows), len(per_model)), "",
         "| Block | Versions with this block | Versions where it is the first blocker |", "|---|---|---|"]
    order_p = ["F", "B", "A", "C", "D", "E", "other", "none"]
    for b in ORDER + ["other"]:
        L.append("| %s %s | %d | %d |" % (b, NAMES.get(b, "unexplained"), tot_any[b], prim.get(b, 0)))
    L += ["", "First blocker order used: F, B, A, C, D, E (a name that differs outright is reported before anything else). The old linker linked %d versions on the "
          "list pages (block B versions are among them: they link, then the page-name check discards the page)." % sum(1 for r in rows if r["old_linker"] == "links"), "",
          "## Per model", "", "| Model | CarWale versions | CarDekho variants | Blocks (version counts) |", "|---|---|---|---|"]
    for make, model, n, k in per_model:
        rs = [r for r in rows if r["model"] == model and r["make"] == make]
        cnt = {b: sum(1 for r in rs if b in r["blocks"]) for b in ORDER + ["other"] if any(b in r["blocks"] for r in rs)}
        L.append("| %s %s | %d | %d | %s |" % (make, model, n, k, ", ".join("%s %d" % (b, n_) for b, n_ in cnt.items()) or "none"))
    L += ["", "## Every CarWale version", "", "| Model | CarWale version (fuel, price) | Best CarDekho candidate (fuel, price) | Old linker | Blocks | Detail |", "|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s%s (%s, %s) | %s (%s, %s) | %s | %s | %s |" % (
            r["model"], r["carwale"], " [special]" if r["special"] else "", r["cw_fuel"], r["cw_price"], r["cd"] or "-", r["cd_fuel"] or "-",
            r["cd_price"], r["old_linker"], ",".join(r["blocks"]) or "-", r["notes"].replace("|", "/")))
    L += ["", "## What the table shows beyond the plan", "",
          "- **XUV400 (B)** is the only block where the *list* names agree: the old linker links all 5 versions, then the page-name check discards each variant page "
          "(the variant page prints `345 kWh` for 34.5 and `394 kWh` for 39.4).",
          "- **ZR-V and X-Trail** are listed in the plan as descriptor cases (D) but the descriptors are not what blocks them: CarWale's name has the word `Sport` (ZR-V) or "
          "only fuel and gearbox words (X-Trail), CarDekho's has `Hybrid` or `STD`. After every fold the trim words still differ (`sport` vs none; none vs `std`), so they are **F**. "
          "No rule in the plan links them; they go to review.",
          "- **Camry**: `Elegant` vs `Elegance` is F, as the plan says. `Sprint Edition ... Dual Tone` has the same price as CarDekho's `Sprint Edition`; the only differences are the hybrid label (C) "
          "and CarWale's `Dual Tone`. Colour names (`Platinum White Pearl`) are F.",
          "- **`Dual Tone` on one site only** (Fortuner Legender 2 versions, Camry Sprint, Comet 2, Urban Cruiser Ebella E3) is not in the plan's descriptor list. It is the whole reason Fortuner Legender "
          "cannot link, so it is listed here as D and handled as a separate, price-guarded rule (see the commit message and the rule list in `match.py`).",
          "- **`with No Charger`** (XUV 3XO EV, 2 versions): `trim_tokens` already drops `no charger` but leaves the word `with`. Not in the plan; found by this table.",
          "- **BE 6 Sporteq `11.2kW Charger` versions (10) and XUV 3XO EV `with Charger` (2)** carry a charger word CarDekho does not (F); their prices also differ the other way (E). They stay unlinked.",
          "- **ZS EV colour names** (`Dark Grey`, `Iconic Ivory`) are F.",
          "- **Hector Tomahawk PHEV**: besides C and `Plug-in` (D), CarDekho says `7-Seater` and CarWale gives no seat count; the existing implied-seat rule needs an agreeing price, and the prices differ (E).",
          "- **Creta Electric `Excellence 51.4 kWh Dual Tone`** (CarWale 2,218,500) has no CarDekho counterpart: the nearest name is a 42 kWh `Excellence HC DT` at the same price. The batteries differ, so it must stay unlinked.",
          ""]
    open(out_md, "w").write("\n".join(L) + "\n")
    if out_json:
        json.dump(rows, open(out_json, "w"), indent=1, default=str)
    return tot_any, prim, len(rows)


if __name__ == "__main__":
    print(main(*sys.argv[1:]))
