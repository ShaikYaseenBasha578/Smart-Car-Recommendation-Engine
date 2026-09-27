import sqlite3
import re
from difflib import SequenceMatcher
from knowledge_base.ingestion.common.resolver import validate_structured

conn = sqlite3.connect("scratch/test_resolver.sqlite")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT g.id FROM generation g JOIN model m ON g.model_id = m.id WHERE m.name='Swift' ORDER BY g.id DESC LIMIT 1")
gen_id = cur.fetchone()[0]

# mock fetch all_variants
cur.execute('''
    SELECT v.id, v.name, pt.fuel_type, pt.engine_cc, pt.power_bhp, v.transmission, v.price_ex_showroom, v.base_variant_id
    FROM variant v
    JOIN powertrain pt ON v.powertrain_id = pt.id
    WHERE v.model_id = 1 AND v.generation_id = ?
''', (gen_id,))
all_variants = cur.fetchall()

def normalize_tokens(s):
    s = s.replace('-', ' ').lower()
    s = s.replace('manual', 'mt').replace('automatic', 'at')
    s = re.sub(r'\b\d\.\d+l\b', '', s)
    s = s.replace('turbo', '').replace('vtvt', '').replace('mpi', '').replace('crdi', '')
    s = s.replace('+', ' plus ')
    s = s.replace('(o)', ' optional ')
    
    tokens = set(s.split())
    config_words = {'petrol', 'diesel', 'cng', 'ev', 'mt', 'at', 'cvt', 'dct', 'amt', 'awd', '4x4', 'fwd', 'rwd', 'hybrid', 'electric'}
    
    identity_tokens = tokens - config_words
    if not identity_tokens:
        return tokens
    return identity_tokens

for c in all_variants:
    warnings = validate_structured(c, 'CNG', 'MT', 1197, None)
    if warnings: continue
    
    t1 = normalize_tokens('VXi CNG Manual')
    t2 = normalize_tokens(c['name'])
    print(f"Variant: {c['name']} | T1: {t1} | T2: {t2}")

