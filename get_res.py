import sqlite3
import json

db_dry = "scratch/phase6_swift_dry_run.sqlite"
conn = sqlite3.connect(db_dry)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id FROM source WHERE name='oem'")
oem_source_id = cur.fetchone()[0]

cur.execute('''
    SELECT so.raw_name, so.resolution_status, v.name as canon_name, v.transmission, so.id, so.raw_payload
    FROM source_observation so
    LEFT JOIN variant v ON so.resolved_variant_id = v.id
    WHERE so.source_id = ?
    ORDER BY so.id DESC LIMIT 9
''', (oem_source_id,))
rows = [dict(r) for r in cur.fetchall()]
with open("scratch/phase6_swift_dry_run_results.json", "w") as f:
    json.dump(rows, f, indent=2)

prov = []
for r in rows:
    cur.execute("SELECT field_name, accepted_value, decision, decision_reason FROM field_provenance WHERE source_observation_id = ?", (r['id'],))
    prov.extend([dict(p) for p in cur.fetchall()])
with open("scratch/phase6_swift_dry_run_prov.json", "w") as f:
    json.dump(prov, f, indent=2)
