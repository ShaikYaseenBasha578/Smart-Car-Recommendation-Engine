import sys
import os
import sqlite3
sys.path.append(os.getcwd())

from knowledge_base.ingestion.common.resolver import resolve_variant

conn = sqlite3.connect("knowledge_base/carrec_kb.db")
conn.row_factory = sqlite3.Row

cur = conn.cursor()
cur.execute("SELECT v.name, pt.fuel_type, pt.engine_cc, v.transmission FROM variant v JOIN model m ON v.model_id = m.id JOIN powertrain pt ON v.powertrain_id = pt.id WHERE m.name = 'Fronx'")
print("DB Fronx variants:")
for r in cur.fetchall():
    print(r['name'], r['fuel_type'], r['transmission'])

v_id, status, cand = resolve_variant(
    conn, "maruti-suzuki", "fronx", "Sigma", "sigma", 
    "CNG", "Manual", None, None, 
    generation_id=None, active_only=False, source_name='oem',
    engine_name="1.2L", edition=None
)
print(f"\nResolve Sigma CNG MT 1.2L -> {status}")
if cand:
    print("Candidates:")
    for c in cand[:3]:
        print(c['v_name'], c['score'])
