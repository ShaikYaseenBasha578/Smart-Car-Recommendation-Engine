import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)), "..")))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import sys
import os
import sqlite3
sys.path.append(os.getcwd())
from knowledge_base.ingestion.common.resolver import compute_similarity, validate_structured

conn = open_kb(KB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT v.id, v.name, pt.fuel_type, pt.engine_cc, v.transmission FROM variant v JOIN model m ON v.model_id = m.id JOIN powertrain pt ON v.powertrain_id = pt.id WHERE m.name = 'Aura'")
all_variants = [dict(r) for r in cur.fetchall()]

candidates = []
for c in all_variants:
    if validate_structured(c, "Petrol", "Manual", None, None):
        continue
    score = compute_similarity("SX", c['name'])
    candidates.append((score, c['name']))

candidates.sort(key=lambda x: x[0], reverse=True)
for c in candidates[:3]:
    print(c)
