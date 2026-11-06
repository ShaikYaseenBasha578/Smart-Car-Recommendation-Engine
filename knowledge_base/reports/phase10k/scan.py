import sqlite3, json, re, csv
from collections import Counter, defaultdict
db=sqlite3.connect("q.db"); db.row_factory=sqlite3.Row
FEAT={"cruise_control":r"cruise","paddle_shifters":r"paddle","sunroof":r"sunroof","heads_up_display":r"head.?up|\bhud\b","wireless_charging":r"wireless (phone |smartphone )?charg","ventilated_front_seats":r"ventilat","tyre_pressure_monitoring_system":r"tyre pressure|tpms","android_auto":r"android","apple_carplay":r"carplay","automatic_climate_control":r"auto(matic)? (climate|temperature|ac)|climat|fatc","rear_camera":r"rear (view )?camera|reverse (parking )?camera","hill_assist":r"hill","esc":r"\besc\b|stability","rear_ac_vents":r"rear ac|ac vents","connected_car_features":r"connected|bluelink|suzuki connect","adas_available":r"adas","camera_360":r"360","drive_modes":r"drive mode"}
Q=re.compile(r"\b(at|amt|ags|cvt|ivt|dct|dsg|mt|manual|automatic|diesel|petrol|cng|turbo|only)\b|\^|\*|†|#|\$|~",re.I)
rows=db.execute("""select o.id, m.name model, v.id vid, v.name vname, v.transmission tr, p.fuel_type fuel, o.raw_payload from source_observation o join variant v on v.id=o.resolved_variant_id join model m on m.id=v.model_id join powertrain p on p.id=v.powertrain_id where o.source_id=6 and o.extraction_method='rsc_payload' order by m.name, v.id""").fetchall()
out=[]
for r in rows:
    p=json.loads(r["raw_payload"]); p=json.loads(p) if isinstance(p,str) else p
    for k,val in p.items():
        if k in("raw_variant_name","powertrain_type","transmission","fuel_type","engine_name","edition","variant_name") or not isinstance(val,str): continue
        for f,rx in FEAT.items():
            if re.search(rx,k,re.I) and (Q.search(val) or Q.search(k)):
                cur=db.execute(f'select "{f}" from v_variant_canonical_q where id=?',(r["vid"],)).fetchone()[0] if f in [c[1] for c in db.execute("pragma table_info(v_variant_canonical_q)")] else None
                out.append((r["model"],r["vid"],r["vname"],r["tr"],r["fuel"],f,cur,k[:60],val[:30]))
print(len(rows),"obs;",len(out),"hits")
for o in out: print(o)
