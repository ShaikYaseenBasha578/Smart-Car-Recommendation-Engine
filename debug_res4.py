import sqlite3
from knowledge_base.ingestion.common.resolver import validate_structured
conn = sqlite3.connect("scratch/test_resolver.sqlite")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('''
    SELECT v.id, v.name, pt.fuel_type, pt.engine_cc, pt.power_bhp, v.transmission, v.price_ex_showroom, v.base_variant_id
    FROM variant v
    JOIN powertrain pt ON v.powertrain_id = pt.id
    WHERE v.id = 63
''')
c = cur.fetchone()
print("c['fuel_type']:", c['fuel_type'])
print("c['transmission']:", c['transmission'])
print("c['engine_cc']:", c['engine_cc'])

warnings = validate_structured(c, 'CNG', 'MT', 1197, None)
print("Warnings:", warnings)
