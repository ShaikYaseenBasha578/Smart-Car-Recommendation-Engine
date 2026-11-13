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
    for v in (m2 or {}).get("variants", []):
        if v["status"] != "CURRENT":
            continue
        cd_vars.append({"name": v["name"], "fuel": v["fuel"], "transmission": c.transmission(v["sub"], v["name"], v["fuel"]),
                        "price": v["price"], "engine_cc": c.num(v["sub"]) if "cc" in v["sub"] else None, "url": v["url"]})
    fp = fingerprint([[v["id"], v["name"], v["status"], v["fields"]] for v in m["versions"]] +
                     [[v["name"], v["price"]] for v in cd_vars])
    st = state.get("%s/%s" % (make, key)) or {}
    out = {"model": m, "versions": [], "problems": problems, "fingerprint": fp, "changed": st.get("fingerprint") != fp,
           "cw_url": item["cw"]["url"], "cd_url": item["cd"]["url"], "launched": m["launched"], "brochure": m.get("brochure")}
    used = set()
    for v in m["versions"]:
        if v["status"] != "current":
            continue
        f = v["fields"]
        rec = {"name": v["name"], "cw_id": v["id"], "special": v["special"], "fields_cw": f, "fields_cd": None,
               "obs_cd": None, "link_reason": None,
               "obs_cw": {"source": "carwale", "raw_name": v["name"], "url": "%s#vid=%s" % (item["cw"]["url"], v["id"]),
                          "observed_at": meta["fetched_at"], "method": M_CW,
                          "payload": dict(v["raw"], page_sha256=meta["sha256"])}}
        target = {"name": v["name"], "fuel": f.get("fuel_type"), "transmission": f.get("transmission"),
                  "price": f.get("price_ex_showroom"), "engine_cc": f.get("engine_cc")}
        pool = [x for x in cd_vars if x["url"] not in used]
        hit, why = match.link(target, pool, item["make"] + " " + item["model"], need_price=True, price_tol=cfg.get("link_price_tolerance", 0.005))
        rec["link_reason"] = why
        if hit:
            used.add(hit["url"])
            vp, vmeta = fetcher.get(hit["url"], max_age_days=rd["spec"])
            pv = cd.parse_variant(vp) if vp else None
            if not pv:
                problems.append("CarDekho variant page unreadable: %s" % hit["url"])
            elif _page_name(pv["name"]) != _page_name(hit["name"]):
                problems.append("CarDekho served %r for %r; not used" % (pv["name"], hit["name"]))   # page check
            else:
                fields = dict(pv["fields"])
                if hit["price"]:
                    fields["price_ex_showroom"] = hit["price"]
                rec["fields_cd"] = fields
                rec["cd_name"] = hit["name"]
                rec["obs_cd"] = {"source": "cardekho", "raw_name": hit["name"], "url": hit["url"],
                                 "observed_at": vmeta["fetched_at"], "method": M_CD,
                                 "payload": {"specs": pv["raw"], "ex_showroom_price_from_model_page": hit["price"],
                                             "model_page": item["cd"]["url"], "page_sha256": vmeta["sha256"]}}
        out["versions"].append(rec)
    out["cd_unlinked"] = [x["name"] for x in cd_vars if x["url"] not in used]
    return out
