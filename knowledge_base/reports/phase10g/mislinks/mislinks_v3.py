"""Read-only: flag aggregator observations whose raw name contradicts the resolved variant (fuel / gearbox / trim),
then list the canonical cells (v_variant_canonical_q) whose provenance is one of those observations."""
import sqlite3, sys, re, json
db = sqlite3.connect(sys.argv[1]); db.row_factory = sqlite3.Row
def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower().replace("+", "plus"))
AUTO = re.compile(r"\b(at|amt|ags|dct|dca|dsg|cvt|ivt|e-?cvt|automatic|tc|torque converter)\b|\bat\b|\(dca\)|\bauto\b", re.I)
MAN = re.compile(r"\b(mt|manual|imt)\b", re.I)
def fuel_of(raw):
    r = raw.lower()
    if "cng" in r: return "cng"
    if re.search(r"\bev\b|electric|kwh", r): return "electric"
    if "diesel" in r or re.search(r"\b1\.5 ?d\b|crdi|\bd\b", r): return "diesel"
    if "hybrid" in r and "mild" not in r and "smart hybrid" not in r: return "hybrid"
    if "petrol" in r or "turbo" in r: return "petrol"
    return None
KB_FUEL = {"Petrol": "petrol", "Diesel": "diesel", "CNG": "cng", "Electric": "electric", "Petrol Hybrid": "hybrid",
           "Diesel Mild Hybrid": "diesel", "Flex Fuel": "petrol"}
rows = db.execute("""select o.id oid, s.name src, o.raw_name, o.resolution_status st, v.id vid, v.name vname, v.transmission tr,
    p.fuel_type fuel, m.name model from source_observation o join source s on s.id=o.source_id
    join variant v on v.id=o.resolved_variant_id join model m on m.id=v.model_id left join powertrain p on p.id=v.powertrain_id
    where s.name in ('91wheels','v3cars','carwale')""").fetchall()
flags = {}
for r in rows:
    raw, why = r["raw_name"], []
    f = fuel_of(raw); kf = KB_FUEL.get(r["fuel"])
    if f and kf and f != kf and not (f == "petrol" and kf == "hybrid"): why.append(f"fuel {f}≠{kf}")
    auto_raw, man_raw = bool(AUTO.search(raw)), bool(MAN.search(raw))
    kb_auto = r["tr"] not in ("Manual", "iMT")
    if auto_raw and not man_raw and not kb_auto: why.append(f"gearbox auto≠{r['tr']}")
    if man_raw and not auto_raw and kb_auto: why.append(f"gearbox manual≠{r['tr']}")
    # trim: KB trim token = variant name up to first fuel/engine word
    trim = re.split(r"\b(petrol|diesel|cng|electric|turbo|\d\.\d|strong|smart|mild|ev)\b", r["vname"], flags=re.I)[0]
    nt, nr = norm(trim), norm(raw.replace(r["model"], ""))
    if nt and nt not in nr: why.append(f"trim '{trim.strip()}'∉raw")
    if why: flags[r["oid"]] = (r, why)
strong = {k: v for k, v in flags.items() if any(w.startswith(("fuel", "gearbox")) for w in v[1])}
print(f"aggregator obs resolved: {len(rows)}; flagged: {len(flags)} (fuel/gearbox: {len(strong)}, trim-only: {len(flags)-len(strong)})\n")
# canonical cells whose provenance is a flagged obs
cols = {c[1] for c in db.execute("pragma table_info(v_variant_canonical_q)")}
fps = db.execute(f"""select fp.id, fp.variant_id, fp.field_name, fp.accepted_value, fp.decision, fp.source_observation_id oid,
   exists(select 1 from v_active_quarantine q where q.target_table='field_provenance' and q.target_id=fp.id) q
   from field_provenance fp where fp.source_observation_id in ({','.join(map(str, flags)) or 'NULL'})""").fetchall()
print("## provenance rows on flagged obs: decision counts")
from collections import Counter
print(dict(Counter((f["decision"], bool(f["q"])) for f in fps)))
print("\n## CANONICAL cells traced to a flagged obs (decision accepted, fp not quarantined, value == canonical)")
n = 0
for f in fps:
    if f["decision"] != "accepted" or f["q"] or f["field_name"] not in cols: continue
    canon = db.execute(f"select {f['field_name']} from v_variant_canonical_q where id=?", (f["variant_id"],)).fetchone()[0]
    others = db.execute("""select count(*) from field_provenance x where x.variant_id=? and x.field_name=? and x.id<>? and x.decision in ('accepted','confirmed')
        and x.source_observation_id not in (%s)""" % ",".join(map(str, flags)), (f["variant_id"], f["field_name"], f["id"])).fetchone()[0]
    r, why = flags[f["oid"]]
    match = str(canon) == f["accepted_value"] or (canon is not None and f["accepted_value"] is not None and str(canon).rstrip("0").rstrip(".") == str(f["accepted_value"]).rstrip("0").rstrip("."))
    n += 1
    print(f"  v{f['variant_id']} {r['model']} '{r['vname']}' {f['field_name']}={canon!r} (fp {f['id']} value {f['accepted_value']!r}, match={match}) "
          f"<- obs {f['oid']} {r['src']} '{r['raw_name']}' [{'; '.join(why)}] other-support={others}")
print(f"  total: {n}")
print("\n## price: provenance sources for price_ex_showroom:", db.execute("select s.name, count(*) from field_provenance fp join source_observation o on o.id=fp.source_observation_id join source s on s.id=o.source_id where fp.field_name='price_ex_showroom' group by 1").fetchall())
print("\n## flagged obs (fuel/gearbox)")
for k, (r, why) in sorted(strong.items()):
    print(f"  obs {k} {r['src']} {r['st']} '{r['raw_name']}' -> v{r['vid']} {r['model']} '{r['vname']}' ({r['fuel']}, {r['tr']}) [{'; '.join(why)}]")
json.dump({str(k): {"why": v[1], "vid": v[0]["vid"], "src": v[0]["src"]} for k, v in flags.items()}, open("mislinks_flags.json", "w"), indent=0)
