import sqlite3
from knowledge_base.ingestion.common.resolver import resolve_variant

conn = sqlite3.connect("scratch/test_resolver.sqlite")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT g.id FROM generation g JOIN model m ON g.model_id = m.id WHERE m.name='Swift' ORDER BY g.id DESC LIMIT 1")
gen_id = cur.fetchone()[0]

res = resolve_variant(conn, 'maruti-suzuki', 'swift', 'VXi CNG Manual', 'vxi-cng-manual', 'CNG', 'MT', 1197, None, generation_id=gen_id)
print(res)
