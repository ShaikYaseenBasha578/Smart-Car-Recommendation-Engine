import sqlite3, sys, json
db = sqlite3.connect(sys.argv[1])
q = lambda s, *a: db.execute(s, a).fetchall()
src = dict(q("select id, name||'/'||source_type||'/t'||authority_tier from source"))
def obs_for(vids, keys):
    out = []
    for oid, sid, raw, payload, meth, vid, st in q(f"select id, source_id, raw_name, raw_payload, extraction_method, resolved_variant_id, resolution_status from source_observation where resolved_variant_id in ({','.join(map(str,vids))})"):
        try: p = json.loads(payload or '{}')
        except Exception: p = {}
        hit = {k: v for k, v in (p.items() if isinstance(p, dict) else []) if any(x in k.lower() for x in keys)}
        if hit: out.append((oid, src[sid], meth, vid, st, raw[:50], hit))
    return out
def fp_for(vids, field):
    return q(f"""select fp.id, fp.variant_id, fp.accepted_value, fp.decision, fp.decision_reason, fp.source_observation_id,
                 (select reason_code from evidence_quarantine eq where eq.target_table='field_provenance' and eq.target_id=fp.id and released_at is null)
                 from field_provenance fp where field_name=? and variant_id in ({','.join(map(str,vids))}) order by variant_id, fp.id""", field)

print("# Power held: pt 84, 88 (and twin pts for comparison)")
for pt in (84, 88):
    row = q("select p.id, mk.name, m.name, p.fuel_type, p.engine_cc, p.power_bhp, p.torque_nm, p.description from powertrain p join model m on m.id=p.model_id join manufacturer mk on mk.id=m.manufacturer_id where p.id=?", pt)[0]
    users = [r[0] for r in q("select id from variant where powertrain_id=? order by id", pt)]
    print(row, "users", users)
    for o in obs_for(users, ("power", "bhp", "ps", "kw")): print("   obs", o)
    for r in q("select id, column_name, old_value, new_value, reason_code, phase from evidence_amendment where target_table='powertrain' and target_id=?", pt): print("   amend", r)
print("\n# twin powertrains (same cc/fuel family, Maruti/Toyota 1.5)")
for r in q("select p.id, m.name, p.fuel_type, p.engine_cc, p.power_bhp, p.torque_nm from powertrain p join model m on m.id=p.model_id where p.engine_cc between 1460 and 1500 and m.name in ('Grand Vitara','Urban Cruiser Hyryder','Victoris') order by p.fuel_type, m.name"): print("  ", r)

for label, field, vids_sql in [
  ("GV 548/549 km/kg", "mileage_arai_km_per_kg", "select id from variant where id in (548,549)"),
  ("Exter CNG km/kg", "mileage_arai_km_per_kg", "select id from variant where id in (655,657,660,663,666)"),
  ("Nexon CNG km/kg", "mileage_arai_km_per_kg", "select v.id from variant v join powertrain p on p.id=v.powertrain_id join model m on m.id=p.model_id where m.name='Nexon' and p.fuel_type='CNG'"),
  ("WagonR 225 km/kg", "mileage_arai_km_per_kg", "select 225"),
]:
    vids = [r[0] for r in q(vids_sql)]
    print(f"\n# {label}: {vids}")
    print("  canonical_q:", q(f"select id, {field} from v_variant_canonical_q where id in ({','.join(map(str,vids))})"))
    for r in fp_for(vids, field): print("  fp", r)
    for o in obs_for(vids, ("km_per_kg", "kmkg", "km/kg", "cng", "mileage")): print("  obs", o)
