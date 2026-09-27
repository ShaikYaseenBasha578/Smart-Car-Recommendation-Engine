import sqlite3
from knowledge_base.ingestion.common.resolver import resolve_variant

conn = sqlite3.connect("scratch/test_blockers.sqlite")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT m.id, mfr.name, m.name FROM model m JOIN manufacturer mfr ON m.manufacturer_id = mfr.id")
print("Models:", [dict(r) for r in cur.fetchall()])
cur.execute("SELECT v.id, v.model_id, v.generation_id, v.name FROM variant v")
print("Variants:", [dict(r) for r in cur.fetchall()])
