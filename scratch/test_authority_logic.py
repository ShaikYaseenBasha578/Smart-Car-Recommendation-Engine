import sqlite3

def run():
    conn = sqlite3.connect("knowledge_base/carrec_kb.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Pick a random variant that has some accepted provenance
    cur.execute('''
        SELECT fp.variant_id, fp.field_name, s.authority_tier, fp.accepted_value
        FROM field_provenance fp
        JOIN source_observation so ON fp.source_observation_id = so.id
        JOIN source s ON so.source_id = s.id
        WHERE fp.decision = 'accepted'
        LIMIT 1
    ''')
    row = cur.fetchone()
    if not row:
        print("No provenance found")
        return
        
    var_id, field, ex_tier, val = row['variant_id'], row['field_name'], row['authority_tier'], row['accepted_value']
    print(f"Found var={var_id}, field={field}, val={val}, tier={ex_tier}")
    
    cur.execute('''
        SELECT s.authority_tier 
        FROM field_provenance fp
        JOIN source_observation so ON fp.source_observation_id = so.id
        JOIN source s ON so.source_id = s.id
        WHERE fp.variant_id = ? AND fp.field_name = ? AND fp.decision IN ('accepted', 'confirmed')
        ORDER BY s.authority_tier ASC, fp.decided_at DESC LIMIT 1
    ''', (var_id, field))
    best_tier = cur.fetchone()['authority_tier']
    print(f"Best tier for this field is {best_tier}")
    
run()
