"""Phase 10H, read-only: on a copy of the frozen paper snapshot, find paper-field cells (body_type, fuel, transmission,
seats, price as paper/oracle/feasibility.py reads them) whose only supporting evidence is a mislinked observation.
Usage: paper_check.py <snapshot_copy> <links.tsv> <out.tsv>"""
import csv, json, sqlite3, sys
from collections import Counter
db = sqlite3.connect(sys.argv[1])
links = {int(r["obs"]): r for r in csv.DictReader(open(sys.argv[2]), delimiter="\t")}
BAD = {o for o, r in links.items() if r["cls"] in ("MISLINK_TARGET", "MISLINK_NONE", "EDITION_NOT_IN_KB")}
qobs = {r[0] for r in db.execute("select target_id from evidence_quarantine where target_table='source_observation' and released_at is null")}
qfp = {r[0] for r in db.execute("select target_id from evidence_quarantine where target_table='field_provenance' and released_at is null")}
rows = db.execute("""select v.id, v.base_variant_id, m.body_type, pt.fuel_type, v.transmission, v.seating_capacity, v.price_ex_showroom,
    b.seating_capacity, b.price_ex_showroom from variant v join model m on m.id=v.model_id join powertrain pt on pt.id=v.powertrain_id
    left join variant b on b.id=v.base_variant_id""").fetchall()
def eq(a, b):
    if a is None or b is None or a == "": return False
    try: return float(a) == float(b)
    except (TypeError, ValueError): return str(a).strip().lower() == str(b).strip().lower()
v6 = {}
for vid, p in db.execute("select resolved_variant_id, raw_payload from source_observation where source_id=1 and resolved_variant_id is not null"):
    if vid not in qobs: v6[vid] = json.loads(p)
FP_FIELD = {"transmission": "transmission", "seats": "seating_capacity", "price": "price_ex_showroom"}
out, tally = [], Counter()
for vid, base, body, fuel, trans, seats, price, bseats, bprice in rows:
    cells = {"body_type": body, "fuel": fuel, "transmission": trans, "seats": seats if seats is not None else bseats,
             "price": price if price is not None else bprice}
    for field, val in cells.items():
        if val is None: continue
        # body_type is model-level and fuel powertrain-level: an edition shares them with its base, so the base's v6 payload counts
        holders = [vid] + ([base] if base and (field in ("body_type", "fuel") or field in ("seats", "price") and cells[field] != (seats if field == "seats" else price)) else [])
        good, badev = [], []
        for h in holders:  # v6 observation payload of the variant (or of the base it inherits from)
            p = v6.get(h)
            key = {"body_type": "body_type", "fuel": "fuel_type", "transmission": "transmission", "seats": "seating_capacity", "price": "price_ex_showroom"}[field]
            if p and eq(p.get(key), val): good.append(f"v6:obs{h}")
        if field in FP_FIELD:
            for fid, oid, dec, acc, h in db.execute(f"""select fp.id, fp.source_observation_id, fp.decision, fp.accepted_value, fp.variant_id from field_provenance fp
                    where fp.field_name=? and fp.variant_id in ({','.join(map(str, holders))}) and fp.decision in ('accepted','confirmed')""", (FP_FIELD[field],)):
                if fid in qfp or oid in qobs or not eq(acc, val): continue
                (badev if oid in BAD else good).append(f"obs{oid}:{dec}")
        if body is not None and field == "body_type" or field == "fuel":
            pass  # model / powertrain columns: only v6 payload evidence applies
        status = "supported" if good else ("SOLE_MISLINK" if badev else "no_evidence")
        tally[(field, status)] += 1
        if status != "supported":
            out.append(dict(variant=vid, edition_of=base or "", field=field, value=val, status=status, mislinked_evidence=";".join(badev)))
with open(sys.argv[3], "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["variant", "edition_of", "field", "value", "status", "mislinked_evidence"], delimiter="\t"); w.writeheader(); w.writerows(out)
for k in sorted(tally): print(k, tally[k])
print("SOLE_MISLINK cells:", sum(1 for o in out if o["status"] == "SOLE_MISLINK"))
for o in out: print(o)
