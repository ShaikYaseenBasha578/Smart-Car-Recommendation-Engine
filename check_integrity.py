import json
import os
import sqlite3

MANIFEST_PATH = "knowledge_base/sources/oem/brochure_manifest.json"
DB_PATH = "knowledge_base/carrec_kb.db"

with open(MANIFEST_PATH, 'r') as f:
    manifest = json.load(f)
    
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("""
    SELECT mk.name as manufacturer, m.name as model, m.id as model_id
    FROM model m
    JOIN manufacturer mk ON m.manufacturer_id = mk.id
""")
canonical_models = {f"{r[0]}_{r[1]}": dict(zip(['manufacturer', 'model', 'model_id'], r)) for r in c.fetchall()}
conn.close()

orphan_entries = set(manifest.keys()) - set(canonical_models.keys())
missing_models = set(canonical_models.keys()) - set(manifest.keys())

status_counts = {}
for k, v in manifest.items():
    if k in canonical_models:
        s = v.get('status', 'UNPROCESSED')
        status_counts[s] = status_counts.get(s, 0) + 1
        
print("Total Canonical Models:", len(canonical_models))
print("Total Manifest Entries:", len(manifest))
print("Orphan Entries:", orphan_entries)
print("Missing Models:", missing_models)
print("Status Counts:", status_counts)
