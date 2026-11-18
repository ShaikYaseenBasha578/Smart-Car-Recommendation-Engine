"""Stage 2, extraction: for one model, read the two sites' structured payloads and link their variants.
No LLM is used here; values are parsed from the JSON the sites embed. Every value keeps its URL, fetch time and method."""
import hashlib
import json

from . import __version__
from . import match
from .sources import cardekho as cd
from .sources import carwale as cw
from .sources import common as c

M_CW = "kbpipe/%s carwale_model_page_json" % __version__
M_CD = "kbpipe/%s cardekho_variant_page_json" % __version__


def _page_name(s):
    """Name used for the page check; CarDekho writes 'Maruti Suzuki X' in lists and 'Maruti X' on pages."""
    return " ".join(w for w in c.norm_name(s).split() if w != "suzuki")


def _page_name_ok(page_name, hit, model_page_name=""):
    """Page check: the variant page names the variant the list named. Two exact allowances, both only after the plain comparison fails:
    (1) a page may drop the decimal point of the battery ("EC Pro 345 kWh" for 34.5 kWh), read as 34.5 only when the model page's
        own name or sub-line says 34.5;
    (2) the list may omit the model name that the page prints ("Essence 7-Seater" listed, "MG Hector Tomahawk EV Essence 7-Seater" on the
        page): the page name must be exactly the model page's own name followed by the listed name."""
    pn, ln = _page_name(page_name), _page_name(hit["name"])
    if pn == ln:
        return True
    if model_page_name and pn == _page_name(model_page_name) + " " + ln:
        return True
    return c.page_battery_fix(pn, hit.get("battery_kwh")) == ln


def fingerprint(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def model_bundle(item, cfg, fetcher, log, state):
    """Returns {"versions": [...], "problems": [...], "fingerprint", "skipped": bool}.
    Each version: {name, cw_id, fields_cw, obs_cw, fields_cd|None, obs_cd|None, link_reason, special}."""
    make, key = item["make"], item["key"]
    rd = cfg["refresh_days"]
    problems = []
    page, meta = fetcher.get(item["cw"]["url"], max_age_days=rd["model_page"])
    m = cw.parse_model(page) if page else None
    if not m or not m["versions"]:
        return {"versions": [], "problems": ["CarWale model page unreadable: %s" % item["cw"]["url"]], "fingerprint": None}
    page2, meta2 = fetcher.get(item["cd"]["url"], max_age_days=rd["model_page"])
    m2 = cd.parse_model(page2) if page2 else None
    if not m2:
        problems.append("CarDekho model page unreadable: %s" % item["cd"]["url"])
    cd_vars = []
    cur = [v for v in (m2 or {}).get("variants", []) if v["status"] == "CURRENT"]
    site_model = c.common_prefix([v["name"] for v in cur]) or (item["cd"].get("name") or "")   # CarDekho's own spelling
    for v in cur:
        if v["fuel"] == "Petrol" and "hybrid" in v["name"].lower() and not any(w in v["name"].lower() for w in ("mild", "smart")):
            v["fuel"] = "Petrol Hybrid"
        cd_vars.append({"name": v["name"], "fuel": v["fuel"], "transmission": c.transmission(v["sub"], v["name"], v["fuel"]),
                        "price": v["price"], "engine_cc": c.num(v["sub"]) if "cc" in v["sub"] else None, "url": v["url"],
                        "sub": v["sub"], "battery_kwh": c.battery_kwh(v["name"], v["sub"])})
    fp = fingerprint([[v["id"], v["name"], v["status"], v["fields"]] for v in m["versions"]] +
                     [[v["name"], v["price"]] for v in cd_vars])
    st = state.get("%s/%s" % (make, key)) or {}
    out = {"model": m, "versions": [], "problems": problems, "fingerprint": fp, "changed": st.get("fingerprint") != fp,
           "cw_url": item["cw"]["url"], "cd_url": item["cd"]["url"], "launched": m["launched"], "brochure": m.get("brochure")}
    cur_cw = [v for v in m["versions"] if v["status"] == "current"]
    strong_hybrid = bool(cur_cw) and all(v["fields"].get("fuel_type") == "Petrol Hybrid" for v in cur_cw)   # rule 2: every version
    targets = {}
    for v in cur_cw:
        f = v["fields"]
        targets[v["id"]] = {"name": v["name"], "fuel": f.get("fuel_type"), "transmission": f.get("transmission"),
                            "price": f.get("price_ex_showroom"), "engine_cc": f.get("engine_cc"), "battery_kwh": c.battery_kwh(v["name"])}
    mname = " ".join([item["make"], item["model"], site_model])
    tol = cfg.get("link_price_tolerance", 0.005)
    hits, used = {}, set()
    # tier 0 is the original linker, over every version first, so no link that exists today can change; tiers 1 and 2 (the
    # missing-models rules, match.py) then only try the versions it left unlinked, on the candidates it left unused.
    for tier in (0, 1, 2):
        for v in cur_cw:
            if tier and hits[v["id"]][0] is not None:
                continue
            pool = [x for x in cd_vars if x["url"] not in used]
            hit, why = match.link(targets[v["id"]], pool, mname, need_price=True, price_tol=tol, tier=tier,
                                  peers=list(targets.values()), strong_hybrid=strong_hybrid)
            if tier == 0 or hit:
                hits[v["id"]] = (hit, why)
            if hit:
                used.add(hit["url"])
    for v in cur_cw:
        f = v["fields"]
        rec = {"name": v["name"], "cw_id": v["id"], "special": v["special"], "fields_cw": f, "fields_cd": None,
               "obs_cd": None, "link_reason": None, "strong_hybrid_rule": False, "price_disagrees": None,
               "obs_cw": {"source": "carwale", "raw_name": v["name"], "url": "%s#vid=%s" % (item["cw"]["url"], v["id"]),
                          "observed_at": meta["fetched_at"], "method": M_CW,
                          "payload": dict(v["raw"], page_sha256=meta["sha256"])}}
        hit, why = hits[v["id"]]
        rec["link_reason"] = why
        if hit:
            vp, vmeta = fetcher.get(hit["url"], max_age_days=rd["spec"])
            pv = cd.parse_variant(vp) if vp else None
            rule2 = "strong-hybrid fuel" in rec["link_reason"]
            if not pv:
                problems.append("CarDekho variant page unreadable: %s" % hit["url"])
            elif not _page_name_ok(pv["name"], hit, (m2 or {}).get("name")):
                problems.append("CarDekho served %r for %r; not used" % (pv["name"], hit["name"]))   # page check
            elif rule2 and pv["fields"].get("fuel_type") not in ("Petrol", "Petrol Hybrid"):
                problems.append("CarDekho page for %r says fuel %r, which contradicts the strong-hybrid link; not used" % (hit["name"], pv["fields"].get("fuel_type")))
                rec["link_reason"] = "refused: CarDekho page fuel contradicts the strong-hybrid rule"
            else:
                fields = dict(pv["fields"])
                if hit["price"]:
                    fields["price_ex_showroom"] = hit["price"]
                if rule2:
                    # rule 2: the fuel value is CarWale's. CarDekho's "Petrol" is not written; the link is the agreement.
                    rec["strong_hybrid_rule"] = {"cardekho_fuel": fields.get("fuel_type"), "carwale_fuel": targets[v["id"]]["fuel"]}
                    fields["fuel_type"] = targets[v["id"]]["fuel"]
                rec["fields_cd"] = fields
                rec["cd_name"] = hit["name"]
                if why.startswith("identity (price differs)"):
                    rec["price_disagrees"] = {"carwale_price": targets[v["id"]]["price"], "cardekho_price": hit["price"],
                                              "cardekho_url": hit["url"]}
                rec["obs_cd"] = {"source": "cardekho", "raw_name": hit["name"], "url": hit["url"],
                                 "observed_at": vmeta["fetched_at"], "method": M_CD,
                                 "payload": {"specs": pv["raw"], "ex_showroom_price_from_model_page": hit["price"],
                                             "model_page": item["cd"]["url"], "page_sha256": vmeta["sha256"]}}
            rec["cd_url"] = hit["url"]
        out["versions"].append(rec)
    out["cd_unlinked"] = [x["name"] for x in cd_vars if x["url"] not in used]
    return out
