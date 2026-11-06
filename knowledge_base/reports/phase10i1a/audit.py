import sqlite3, csv
from collections import Counter
c = sqlite3.connect("q.db"); c.row_factory = sqlite3.Row
print("## (i) edition-candidate path")
known = set(range(814, 834))
eds = c.execute("select v.id, v.name, v.base_variant_id base, v.edition_classification ec, v.created_at, m.name model, (select count(*) from source_observation o where o.resolved_variant_id=v.id and o.source_id=1) v6 from variant v join model m on m.id=v.model_id where v.base_variant_id is not null or v.edition_classification is not null or v.id>812 order by v.id").fetchall()
print("rows with base_variant_id / classification / id>812:", len(eds), "| ids:", [e["id"] for e in eds])
print("outside 814..833:", [dict(e) for e in eds if e["id"] not in known])
print("known ids absent:", sorted(known - {e["id"] for e in eds}))
print("no v6 observation:", [r[0] for r in c.execute("select v.id from variant v where not exists(select 1 from source_observation o where o.resolved_variant_id=v.id and o.source_id=1) order by 1")])
print("ec:", Counter(e["ec"] for e in eds), "created:", Counter((e["created_at"] or "")[:10] for e in eds))
print("base rows with v6 obs among editions:", [e["id"] for e in eds if e["v6"]])
# identity consistency of each edition vs its name
for e in c.execute("select v.id, m.name model, v.name, v.transmission, p.engine_cc, p.fuel_type, b.name base from variant v join model m on m.id=v.model_id join powertrain p on p.id=v.powertrain_id join variant b on b.id=v.base_variant_id order by v.id"):
    print(" ", e["id"], e["model"], "|", e["name"], "|", e["transmission"], e["engine_cc"], e["fuel_type"], "| base:", e["base"])
print("## (ii) canonical cells from resolved_with_warning")
print("obs by status:", c.execute("select s.name, o.resolution_status, count(*) from source_observation o join source s on s.id=o.source_id group by 1,2").fetchall())
qo = {r[0] for r in c.execute("select target_id from v_active_quarantine where target_table='source_observation'")}
qf = {r[0] for r in c.execute("select target_id from v_active_quarantine where target_table='field_provenance'")}
cols = {r[1] for r in c.execute("pragma table_info(v_variant_canonical_q)")}
rows = c.execute("""select fp.id fp, fp.variant_id vid, fp.field_name f, fp.accepted_value val, fp.decision dec, fp.source_observation_id oid, o.raw_name raw, s.name src
  from field_provenance fp join source_observation o on o.id=fp.source_observation_id join source s on s.id=o.source_id
  where o.resolution_status='resolved_with_warning'""").fetchall()
print("fp rows on rwarn obs:", len(rows), Counter(r["dec"] for r in rows), "| obs quarantined:", sum(r["oid"] in qo for r in rows), "| fp quarantined:", sum(r["fp"] in qf for r in rows))
out = []
for r in rows:
    if r["dec"] != "accepted" or r["f"] not in cols: continue
    live = r["oid"] not in qo and r["fp"] not in qf
    canon = c.execute(f'select "{r["f"]}" from v_variant_canonical_q where id=?', (r["vid"],)).fetchone()[0]
    match = canon is not None and (str(canon) == r["val"] or (r["val"] not in (None,"") and _f if False else False))
    try: match = canon is not None and float(canon) == float(r["val"])
    except (TypeError, ValueError): match = canon is not None and str(canon) == r["val"]
    other = c.execute("""select count(*) from v_live_evidence e where e.variant_id=? and e.field_name=? and e.decision in ('accepted','confirmed') and e.observation_id<>?""", (r["vid"], r["f"], r["oid"])).fetchone()[0]
    agree = c.execute("""select count(*) from v_live_evidence e where e.variant_id=? and e.field_name=? and e.decision in ('accepted','confirmed') and e.observation_id<>? and e.accepted_value=?""", (r["vid"], r["f"], r["oid"], r["val"])).fetchone()[0]
    out.append(dict(fp=r["fp"], vid=r["vid"], field=r["f"], val=r["val"], canon=canon, src=r["src"], oid=r["oid"], raw=r["raw"], obs_live=live, in_canonical=match, other_live=other, other_agree=agree))
print("accepted fp rows on rwarn obs:", len(out))
print(Counter((o["obs_live"], o["in_canonical"]) for o in out))
sole = [o for o in out if o["obs_live"] and o["in_canonical"] and not o["other_agree"]]
print("live, in canonical:", sum(o["obs_live"] and o["in_canonical"] for o in out), "| with no other agreeing live evidence:", len(sole), Counter(o["field"] for o in sole), Counter(o["src"] for o in sole))
with open("rwarn_cells.tsv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]),delimiter="\t"); w.writeheader(); w.writerows(out)
