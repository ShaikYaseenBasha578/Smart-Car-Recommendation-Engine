import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)), "..")))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import sqlite3
import json

conn = open_kb(KB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
    SELECT mk.name as manufacturer, m.name as model, m.id as model_id
    FROM model m
    JOIN manufacturer mk ON m.manufacturer_id = mk.id
    ORDER BY mk.name, m.name
""")
rows = c.fetchall()
models = [dict(r) for r in rows]

print(f"Total models: {len(models)}")
with open('scratch/models.json', 'w') as f:
    json.dump(models, f, indent=2)
