import sqlite3

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
c = conn.cursor()
def q_val(query):
    c.execute(query)
    res = c.fetchone()
    return res[0] if res else 0

cw_trans_recovery = q_val("""
    SELECT COUNT(DISTINCT resolved_variant_id) 
    FROM source_observation 
    WHERE source_id=4 AND resolution_status='resolved'
    AND resolved_variant_id NOT IN (
        SELECT resolved_variant_id FROM source_observation 
        WHERE source_id=3 AND resolution_status='resolved' AND resolved_variant_id IS NOT NULL
    )
    AND resolved_variant_id IN (
        SELECT id FROM variant WHERE transmission IN ('DCT', 'Torque Converter', 'CVT', 'AMT')
    )
""")
print(f"Transmission recovered: {cw_trans_recovery}")
