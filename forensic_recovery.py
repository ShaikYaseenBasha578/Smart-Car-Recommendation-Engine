import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)))))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import sqlite3

conn = open_kb(KB_PATH)
c = conn.cursor()

def q_val(query, params=()):
    c.execute(query, params)
    res = c.fetchone()
    return res[0] if res else 0

# Variants observed by CW
cw_variants = q_val("""
    SELECT COUNT(DISTINCT resolved_variant_id) 
    FROM source_observation 
    WHERE source_id=4 AND resolution_status='resolved'
""")

# Variants observed by V3Cars
v3_variants = q_val("""
    SELECT COUNT(DISTINCT resolved_variant_id) 
    FROM source_observation 
    WHERE source_id=3 AND resolution_status='resolved'
""")

# Variants recovered by CW (Observed by CW but NOT observed by V3Cars)
recovered = q_val("""
    SELECT COUNT(DISTINCT resolved_variant_id) 
    FROM source_observation 
    WHERE source_id=4 AND resolution_status='resolved'
    AND resolved_variant_id NOT IN (
        SELECT resolved_variant_id FROM source_observation 
        WHERE source_id=3 AND resolution_status='resolved' AND resolved_variant_id IS NOT NULL
    )
""")

print(f"CW Variants: {cw_variants}")
print(f"V3Cars Variants: {v3_variants}")
print(f"Recovered (CW only): {recovered}")

# Transmission mismatch
# In Phase 4, V3Cars had "transmission mismatches" (e.g. V3Cars said Automatic, but V6 was DCT). 
# V3Cars threw 'unresolvable' for these. 
# Did CW resolve them? CW provides specific transmissions.
# Since we can't link the exact V3Cars unresolvable observation directly, we can count how many canonical variants were missing V3Cars, but gained CW, and have transmission in (DCT, TC, CVT).
cw_trans_recovery = q_val("""
    SELECT COUNT(DISTINCT resolved_variant_id) 
    FROM source_observation 
    WHERE source_id=4 AND resolution_status='resolved'
    AND resolved_variant_id NOT IN (
        SELECT resolved_variant_id FROM source_observation 
        WHERE source_id=3 AND resolution_status='resolved' AND resolved_variant_id IS NOT NULL
    )
    AND resolved_variant_id IN (
        SELECT id FROM variant WHERE transmission IN ('Automatic (DCT)', 'Automatic (TC)', 'Automatic (CVT)')
    )
""")

print(f"Transmission recovered (CW only, auto specific): {cw_trans_recovery}")
