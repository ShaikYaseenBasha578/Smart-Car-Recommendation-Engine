"""Stage 1, discovery: which models are on sale, according to two listing sites, against what the KB holds.

A model counts as on sale only when BOTH sites list it as current. Everything else is reported with a reason and
never written."""
import re

from .sources import cardekho as cd
from .sources import carwale as cw

ALIASES = {  # listing name -> KB name, where the sites and the KB spell one model differently. Logged in the report.
    "wagonr": "wagonr", "scorpion": "scorpion", "tharroxx": "tharroxx", "taisor": "urbancruisertaisor",
    "scorpio": "scorpioclassic", "tharog": "thar", "xuv400ev": "xuv400", "landcruiser300": "landcruiser",
    "evitara": "evitara", "kwid": "kwid", "ioniq5": "ioniq5",
}


def model_key(name, cfg=None):
    k = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    if k.startswith("suzuki"):
        k = k[6:]
    al = dict(ALIASES)
    al.update((cfg or {}).get("model_aliases") or {})
    return al.get(k, k)


def listings(cfg, fetcher, log):
    """{make: {key: {"cw": entry|None, "cd": entry|None}}} plus fetch failures."""
    out, failed = {}, []
    age = cfg["refresh_days"]["listing"]
    for make in cfg["scope_makes"]:
        models = out.setdefault(make, {})
        for mod, tag in ((cw, "cw"), (cd, "cd")):
            url = mod.brand_url(make)
            page, meta = fetcher.get(url, max_age_days=age)
            rows = mod.parse_brand(page, make) if page else None
            if rows is None:
                failed.append((mod.NAME, make, url))
                log("discover", "%s brand page for %s could not be read" % (mod.NAME, make))
                continue
            for r in rows:
                r["fetched_at"] = meta["fetched_at"]
                r["brand_url"] = url
                e = models.setdefault(model_key(r["name"], cfg), {"cw": None, "cd": None})
                if e[tag] is None or (r["status"] == "current" and e[tag]["status"] != "current"):
                    e[tag] = r
    return out, failed


def classify(cfg, kbconn, lst, failed):
    """One item per model seen anywhere: kind, reason and what the next stages need."""
    kb = {}
    for r in kbconn.execute("select mo.id, m.name make, mo.name model, mo.body_type, "
                            "(select count(*) from variant v where v.model_id=mo.id and v.is_discontinued=0) live, "
                            "(select min(o.observed_at) from source_observation o join variant v on v.id=o.resolved_variant_id "
                            " where v.model_id=mo.id) first_obs "
                            "from model mo join manufacturer m on m.id=mo.manufacturer_id"):
        kb[(r["make"], model_key(r["model"], cfg))] = dict(r)
    failed_makes = {(s, m) for s, m, _ in failed}
    items = []
    for make, models in lst.items():
        blind = [s for s in ("carwale", "cardekho") if (s, make) in failed_makes]
        for key, e in sorted(models.items()):
            a, b = e["cw"], e["cd"]
            cur_a, cur_b = bool(a and a["status"] == "current"), bool(b and b["status"] == "current")
            k = kb.get((make, key))
            it = {"make": make, "key": key, "model": k["model"] if k else (a or b)["name"], "in_kb": bool(k),
                  "kb_model_id": k["id"] if k else None, "cw": a, "cd": b,
                  "min_price": (a or {}).get("min_price") or (b or {}).get("min_price"),
                  "body_type": (cw.BODY.get(a.get("body_style_id")) if a else None) or (b or {}).get("body_type")}
            if a and b and a.get("body_style_id") is not None and b.get("body_type") and cw.BODY.get(a["body_style_id"]) \
                    and cw.BODY.get(a["body_style_id"]) != b["body_type"]:
                it["body_type_conflict"] = [cw.BODY.get(a["body_style_id"]), b["body_type"]]
            if blind:
                it["kind"], it["reason"] = "UNKNOWN", "listing unreadable on %s" % ", ".join(blind)
            elif cur_a and cur_b:
                if k:
                    it["kind"], it["reason"] = "EXISTING", "listed as current on both sites"
                    if a.get("launched") and k.get("first_obs") and a["launched"] > k["first_obs"][:10]:
                        it["facelift"] = "CarWale gives launch date %s, after the KB's first data for this model (%s)" % (
                            a["launched"], k["first_obs"][:10])
                elif it["min_price"] and it["min_price"] > cfg["scope_max_base_price"]:
                    it["kind"], it["reason"] = "OUT_OF_SCOPE", "base price Rs %d is above the Rs %d cap" % (
                        it["min_price"], cfg["scope_max_base_price"])
                elif not it["min_price"]:
                    it["kind"], it["reason"] = "OUT_OF_SCOPE", "no price listed"
                elif it["body_type"] is None or it.get("body_type_conflict"):
                    it["kind"], it["reason"] = "REVIEW_MODEL", "body type unknown or the sites disagree: %s" % (
                        it.get("body_type_conflict") or [(a or {}).get("body_style_id"), (b or {}).get("vehicle_type")])
                elif re.search(r"\b(\d(st|nd|rd|th) gen|old|new|20\d\d)\b", it["model"].lower()):
                    it["kind"], it["reason"] = "REVIEW_MODEL", "name carries a generation marker: new model, or a generation of one the KB has?"
                else:
                    it["kind"], it["reason"] = "NEW_MODEL", "listed as current on both sites, not in the KB"
            elif cur_a or cur_b:
                one = "CarWale" if cur_a else "CarDekho"
                other = (b if cur_a else a)
                it["kind"] = "ONE_SITE_ONLY"
                it["reason"] = "current on %s only (other site: %s)" % (one, other["status"] if other else "not listed")
            elif k:
                st = [x["status"] if x else "not listed" for x in (a, b)]
                it["kind"], it["reason"] = "DISCONTINUED_CANDIDATE", "CarWale: %s, CarDekho: %s" % tuple(st)
            else:
                st = (a or b)["status"]
                it["kind"], it["reason"] = ("UPCOMING" if st == "upcoming" else "NOT_ON_SALE"), st
            items.append(it)
        for (mk, key), k in kb.items():
            if mk == make and key not in models:
                items.append({"make": make, "key": key, "model": k["model"], "in_kb": True, "kb_model_id": k["id"],
                              "cw": None, "cd": None, "min_price": None, "body_type": k["body_type"],
                              "kind": "UNKNOWN" if blind else "DISCONTINUED_CANDIDATE",
                              "reason": "in the KB, not listed on either site" if not blind else "listing unreadable"})
    return items
