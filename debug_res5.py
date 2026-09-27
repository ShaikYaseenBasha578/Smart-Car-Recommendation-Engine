import sqlite3
from knowledge_base.ingestion.common.resolver import resolve_variant, compute_similarity, validate_structured
conn = sqlite3.connect("scratch/test_resolver.sqlite")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT g.id FROM generation g JOIN model m ON g.model_id = m.id WHERE m.name='Swift' ORDER BY g.id DESC LIMIT 1")
gen_id = cur.fetchone()[0]
cur.execute('''
    SELECT v.id, v.name, pt.fuel_type, pt.engine_cc, pt.power_bhp, v.transmission, v.price_ex_showroom, v.base_variant_id
    FROM variant v
    JOIN powertrain pt ON v.powertrain_id = pt.id
    WHERE v.model_id = 3 AND v.generation_id = ?
''', (gen_id,))
all_variants = cur.fetchall()

for c in all_variants:
    w = validate_structured(c, 'CNG', 'MT', 1197, None)
    if w: continue
    s = compute_similarity('VXi CNG Manual', c['name'])
    print(c['name'], s)
