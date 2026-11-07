"""Read-only replay of every resolved aggregator observation through the real resolver, with the same arguments each
ingester would pass. Usage (from a worktree root): replay.py <db_copy> <links.tsv> <out.tsv>"""
import csv, json, sqlite3, sys
from collections import Counter
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.carwale.ingest_carwale import resolve_carwale_version, served_page_matches
from knowledge_base.ingestion.v3cars.field_map_v3cars import extract_transmission_from_name, extract_fuel_from_name, extract_engine_cc_from_name, parse_price
from knowledge_base.ingestion.source_91wheels.field_map_91wheels import safe_float
db = sqlite3.connect(sys.argv[1]); db.row_factory = sqlite3.Row
links = {r["obs"]: r for r in csv.DictReader(open(sys.argv[2]), delimiter="\t")}
slug = lambda s: s.lower().replace(" ", "-")
rows = []
for o in db.execute("""select o.id, s.name src, o.raw_name, o.raw_payload, o.source_url, o.resolved_variant_id vid, m.name model, f.name make, v.name vname
    from source_observation o join source s on s.id=o.source_id join variant v on v.id=o.resolved_variant_id join model m on m.id=v.model_id join manufacturer f on f.id=m.manufacturer_id
    where s.name in ('91wheels','v3cars','carwale') order by o.id""").fetchall():
    try:
        p = json.loads(o["raw_payload"] or "{}"); p = json.loads(p) if isinstance(p, str) else p
    except Exception: p = {}
    mk, md, raw = slug(o["make"]), slug(o["model"]), o["raw_name"]
    if o["src"] == "91wheels":
        v = p.get("raw", {}); sp = v.get("specs") if isinstance(v.get("specs"), dict) else {}
        pr = safe_float((v.get("variant_price") or {}).get("ex_showroom_price")) or safe_float(v.get("v_variant_price"))
        r = resolve_variant(db, mk, md, raw, v.get("v_variant_slug", ""), v.get("v_variant_fuel_type", ""), sp.get("transmission_type"), safe_float(sp.get("displacement")), pr, source_name="91wheels")
    elif o["src"] == "v3cars":
        r = resolve_variant(db, mk, md, raw, "", extract_fuel_from_name(raw), extract_transmission_from_name(raw), extract_engine_cc_from_name(raw), parse_price(p.get("ex_showroom_price")), source_name="v3cars")
    else:
        if not served_page_matches(raw, p.get("v_variant_name")):
            rows.append(dict(obs=o["id"], src=o["src"], cls=links[str(o["id"])]["cls"], outcome="PAGE_MISMATCH", current=o["vid"], new="", raw=raw.strip(), current_name=o["vname"], match="page_mismatch")); continue
        r = resolve_carwale_version(db, mk, md, raw, o["source_url"].rstrip("/").split("/")[-1])
    vid, status, base = r
    oc = ("AUTO_SAME" if vid == o["vid"] else "AUTO_OTHER") if vid else {"needs_review": "REVIEW", "edition_candidate": "EDITION", "unresolved": "UNRESOLVED"}[status]
    rows.append(dict(obs=o["id"], src=o["src"], cls=links[str(o["id"])]["cls"], outcome=oc, current=o["vid"], new=vid or "", raw=raw.strip(), current_name=o["vname"], match=r.match_type))
with open(sys.argv[3], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t"); w.writeheader(); w.writerows(rows)
cl = ["OK", "MISLINK_TARGET", "MISLINK_NONE", "EDITION_NOT_IN_KB", "REVIEW"]; oc = ["AUTO_SAME", "AUTO_OTHER", "REVIEW", "EDITION", "UNRESOLVED", "PAGE_MISMATCH"]
t = Counter((r["cls"], r["outcome"]) for r in rows)
print("class".ljust(18) + "".join(x[:13].rjust(14) for x in oc))
for c in cl: print(c.ljust(18) + "".join(str(t[(c, x)]).rjust(14) for x in oc))
print("all".ljust(18) + "".join(str(sum(t[(c, x)] for c in cl)).rjust(14) for x in oc), len(rows))
print("match types", Counter(r["match"] for r in rows)); print("by source auto", Counter((r["src"], r["outcome"]) for r in rows if r["outcome"].startswith("AUTO")))
