"""Build resolver_10i_fixture.json from a COPY of the KB plus the 10H labels. Usage: build_resolver_10i_fixture.py <db_copy> <links.tsv>
Each case holds the arguments an ingester would pass to the resolver, the variant it was linked to in 2026, and its 10H class."""
import csv, json, os, sqlite3, sys
from knowledge_base.ingestion.v3cars.field_map_v3cars import extract_transmission_from_name, extract_fuel_from_name, extract_engine_cc_from_name, parse_price
from knowledge_base.ingestion.source_91wheels.field_map_91wheels import safe_float
db = sqlite3.connect(sys.argv[1]); db.row_factory = sqlite3.Row
links = {r["obs"]: r for r in csv.DictReader(open(sys.argv[2]), delimiter="\t")}
rows = lambda q: [list(r) for r in db.execute(q)]
fx = dict(source=rows("select id, name from source"), manufacturer=rows("select id, name from manufacturer"), model=rows("select id, manufacturer_id, name from model"),
          powertrain=rows("select id, model_id, fuel_type, engine_cc, power_bhp from powertrain"),
          variant=rows("select id, model_id, generation_id, powertrain_id, name, transmission, drivetrain, price_ex_showroom, base_variant_id, is_discontinued from variant"),
          variant_alias=rows("select variant_id, source_id, alias_name, needs_review, is_verified from variant_alias"), cases=[])
slug = lambda s: s.lower().replace(" ", "-")
for o in db.execute("""select o.id, s.name src, o.raw_name, o.raw_payload, o.source_url, o.resolved_variant_id vid, m.name model, f.name make
    from source_observation o join source s on s.id=o.source_id join variant v on v.id=o.resolved_variant_id join model m on m.id=v.model_id join manufacturer f on f.id=m.manufacturer_id
    where s.name in ('91wheels','v3cars','carwale') order by o.id""").fetchall():
    try:
        p = json.loads(o["raw_payload"] or "{}"); p = json.loads(p) if isinstance(p, str) else p
    except Exception: p = {}
    c = dict(obs=o["id"], src=o["src"], make=slug(o["make"]), model=slug(o["model"]), name=o["raw_name"], linked=o["vid"], cls=links[str(o["id"])]["cls"])
    if o["src"] == "91wheels":
        v = p.get("raw", {}); sp = v.get("specs") if isinstance(v.get("specs"), dict) else {}
        c.update(slug=v.get("v_variant_slug", ""), fuel=v.get("v_variant_fuel_type", ""), trans=sp.get("transmission_type"), cc=safe_float(sp.get("displacement")),
                 price=safe_float((v.get("variant_price") or {}).get("ex_showroom_price")) or safe_float(v.get("v_variant_price")))
    elif o["src"] == "v3cars":
        raw = o["raw_name"]
        c.update(slug="", fuel=extract_fuel_from_name(raw), trans=extract_transmission_from_name(raw), cc=extract_engine_cc_from_name(raw), price=parse_price(p.get("ex_showroom_price")))
    else:
        c.update(slug=o["source_url"].rstrip("/").split("/")[-1], served=p.get("v_variant_name"))
    fx["cases"].append(c)
json.dump(fx, open(os.path.join(os.path.dirname(__file__), "resolver_10i_fixture.json"), "w"), separators=(",", ":"))
print(len(fx["cases"]), "cases")
