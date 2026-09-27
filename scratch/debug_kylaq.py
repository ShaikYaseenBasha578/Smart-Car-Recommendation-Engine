import sys
import os
import sqlite3
sys.path.append(os.getcwd())
from knowledge_base.ingestion.common.resolver import validate_structured, compute_similarity

conn = sqlite3.connect("knowledge_base/carrec_kb.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT v.id, v.name, pt.fuel_type, pt.engine_cc, v.transmission FROM variant v JOIN model m ON v.model_id = m.id JOIN powertrain pt ON v.powertrain_id = pt.id WHERE m.name = 'Kylaq'")
all_variants = [dict(r) for r in cur.fetchall()]

variant_name = "Classic"
fuel = "Petrol"
trans = "Manual"

candidates = []
for c in all_variants:
    warnings = validate_structured(c, fuel, trans, None, None)
    if warnings: continue
    score = compute_similarity(variant_name, c['name'])
    candidates.append((score, c['name']))

candidates.sort(key=lambda x: x[0], reverse=True)
print("Candidates for Classic:", candidates[:3])
