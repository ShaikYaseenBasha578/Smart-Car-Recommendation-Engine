import sqlite3, csv
from collections import Counter
c=sqlite3.connect("q.db"); c.row_factory=sqlite3.Row
rows=c.execute("select fp.* from field_provenance fp left join source_observation o on o.id=fp.source_observation_id where fp.source_observation_id is not null and o.id is null").fetchall()
print("orphans",len(rows)," fk_check",len(c.execute("pragma foreign_key_check").fetchall()))
print("decision",Counter(r["decision"] for r in rows)); print("reason",Counter(r["decision_reason"] for r in rows).most_common(8))
print("decided_at days",Counter((r["decided_at"] or "")[:10] for r in rows)); print("obs ids",min(r["source_observation_id"] for r in rows),max(r["source_observation_id"] for r in rows),"distinct",len({r["source_observation_id"] for r in rows}))
print("variants",len({r["variant_id"] for r in rows}))
vm=dict(c.execute("select v.id,m.name from variant v join model m on m.id=v.model_id").fetchall()); print("models",Counter(vm.get(r["variant_id"],"NO VARIANT") for r in rows).most_common(12))
print("fields",Counter(r["field_name"] for r in rows).most_common(14))
qf={x[0] for x in c.execute("select target_id from v_active_quarantine where target_table='field_provenance'")}
print("already quarantined fp",sum(r["id"] in qf for r in rows))
cols={x[1] for x in c.execute("pragma table_info(v_variant_canonical_q)")}
dep=0; acc=[]
for r in rows:
    if r["decision"]!="accepted" or r["field_name"] not in cols: continue
    can=c.execute(f'select "{r["field_name"]}" from v_variant_canonical_q where id=?',(r["variant_id"],)).fetchone()
    can=can[0] if can else None
    try: match=can is not None and float(can)==float(r["accepted_value"])
    except: match=str(can)==r["accepted_value"]
    other=c.execute("select count(*) from v_live_evidence where variant_id=? and field_name=? and decision in ('accepted','confirmed')",(r["variant_id"],r["field_name"])).fetchone()[0]
    if match: acc.append((r["variant_id"],vm.get(r["variant_id"]),r["field_name"],can,other))
print("accepted orphans equal to the canonical value:",len(acc),"| with no other live evidence:",sum(a[4]==0 for a in acc))
for a in acc[:12]: print(" ",a)
print("in v_live_evidence?", c.execute("select count(*) from v_live_evidence e where e.observation_id in (select fp.source_observation_id from field_provenance fp left join source_observation o on o.id=fp.source_observation_id where fp.source_observation_id is not null and o.id is null)").fetchone()[0])
with open("orphans.tsv","w",newline="") as f:
    w=csv.writer(f,delimiter="\t"); w.writerow(rows[0].keys()); w.writerows([tuple(r) for r in rows])
