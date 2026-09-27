import sqlite3
import json

conn = sqlite3.connect("knowledge_base/carrec_kb.db")
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
