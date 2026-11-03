"""Read-only. Usage: mislinks_trace.py <db_copy> > mislinks3.txt
Flags aggregator observations (91wheels / v3cars / carwale) whose raw name contradicts the resolved variant on fuel,
gearbox or trim key, and prints TRACED lines for canonical cells (v_variant_canonical_q) whose accepted,
un-quarantined field_provenance row cites a flagged observation. Helpers come from mislinks_v3.py."""
import re
import sqlite3
import sys

ns = {}
exec(open("mislinks_v3.py").read().split("rows = db.execute")[0].replace("db = sqlite3.connect(sys.argv[1]); db.row_factory = sqlite3.Row", ""), ns)
db = sqlite3.connect(sys.argv[1]); db.row_factory = sqlite3.Row
STOP = r"(petrol|diesel|cng|electric|ev|turbo|tcmpfi|mpfi|tgdi|gdi|crdi|mhawk|mstallion|hybrid|strong|smart|mild|manual|automatic|mt|at|amt|ags|cvt|ivt|dct|dca|dsg|tc|imt|ecvt|2wd|4wd|4x4|4x2|rwd|awd|fwd|\d+|seater|dual|tone|dt|dark|edition|black|camo|red|knight|speed|l)"
def key(s, model):
    for m in (model, model.replace(" ", "")):
        s = re.sub(re.escape(m), " ", s, flags=re.I)
    s = re.sub(r"(\d\.\d) ?l\b", r" \1 l ", s, flags=re.I)
    s = s.replace("+", " plus ").replace("(O)", " o ").replace("(o)", " o ")
    s = re.sub(r"\bopt(ional)?\b", " o ", s, flags=re.I)
    s = re.sub(r"[()\-/,.]", " ", s)
    toks = []
    for t in s.split():
        if re.fullmatch(STOP, t, re.I): break
        toks.append(t.lower())
    return "".join(toks)
rows = db.execute("""select o.id oid, s.name src, o.raw_name, o.resolution_status st, v.id vid, v.name vname, v.transmission tr,
    p.fuel_type fuel, m.name model from source_observation o join source s on s.id=o.source_id
    join variant v on v.id=o.resolved_variant_id join model m on m.id=v.model_id left join powertrain p on p.id=v.powertrain_id
    where s.name in ('91wheels','v3cars','carwale')""").fetchall()
flags = {}
for r in rows:
    raw, why = r["raw_name"], []
    f = ns["fuel_of"](raw); kf = ns["KB_FUEL"].get(r["fuel"])
    if f and kf and f != kf and not (f == "petrol" and kf == "hybrid"): why.append(f"fuel:{f}≠{kf}")
    a, mn = bool(ns["AUTO"].search(raw)), bool(ns["MAN"].search(raw)); kb_auto = r["tr"] not in ("Manual", "iMT")
    if a and not mn and not kb_auto: why.append(f"gearbox:auto≠{r['tr']}")
    if mn and not a and kb_auto: why.append(f"gearbox:manual≠{r['tr']}")
    kk, rk = key(r["vname"], r["model"]), key(raw, r["model"])
    if kk and rk and kk != rk: why.append(f"trim:{rk}≠{kk}")
    if why: flags[r["oid"]] = (r, why)
from collections import Counter
print("resolved aggregator obs", len(rows), "flagged", len(flags), dict(Counter(w.split(":")[0] for _, ws in flags.values() for w in ws)))
cols = {c[1] for c in db.execute("pragma table_info(v_variant_canonical_q)")}
ids = ",".join(map(str, flags))
for f in db.execute(f"""select fp.* from field_provenance fp where decision='accepted' and source_observation_id in ({ids})
    and not exists(select 1 from v_active_quarantine q where q.target_table='field_provenance' and q.target_id=fp.id) order by variant_id"""):
    if f["field_name"] not in cols: continue
    canon = db.execute(f"select {f['field_name']} from v_variant_canonical_q where id=?", (f["variant_id"],)).fetchone()[0]
    if canon is None or float(canon) != float(f["accepted_value"]): continue
    sup = db.execute(f"""select group_concat(s.name||':'||x.decision) from field_provenance x join source_observation o on o.id=x.source_observation_id join source s on s.id=o.source_id
        where x.variant_id=? and x.field_name=? and x.id<>? and x.decision in ('accepted','confirmed') and x.source_observation_id not in ({ids})""",
        (f["variant_id"], f["field_name"], f["id"])).fetchone()[0]
    r, why = flags[f["source_observation_id"]]
    print(f"TRACED|v{f['variant_id']}|{r['model']}|{r['vname']}|{f['field_name']}|{canon}|fp{f['id']}|obs{r['oid']} {r['src']}|{r['raw_name']}|{'; '.join(why)}|other={sup or '-'}")
