import sqlite3
import json

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
c = conn.cursor()

def q_val(query, params=()):
    c.execute(query, params)
    res = c.fetchone()
    return res[0] if res else 0

with open('knowledge_base/carwale_batch_state.json', 'r') as f:
    state = json.load(f)

print("| Model | CW Status | Discovered | Resolved | Unresolved | Editions | New Fields | Rejected | Errors |")
print("|---|---|---|---|---|---|---|---|---|")

c.execute("SELECT id, name, manufacturer_id FROM model")
models = c.fetchall()

for m in models:
    c.execute("SELECT name FROM manufacturer WHERE id=?", (m[2],))
    make_name = c.fetchone()[0]
    canonical_slug = m[1].lower().replace(' ', '-')
    make_slug = make_name.lower().replace(' ', '-')
    model_key = f"{make_slug}_{canonical_slug}"
    
    # Get stats from DB
    # We find all variant IDs for this model
    v_ids = f"SELECT id FROM variant WHERE model_id={m[0]}"
    
    # Editions
    editions = q_val(f"SELECT COUNT(*) FROM variant WHERE model_id={m[0]} AND edition_classification IS NOT NULL")
    
    # New Fields & Rejected
    new_fields = q_val(f"""
        SELECT COUNT(*) FROM field_provenance 
        WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4) 
        AND decision = 'accepted' AND decision_reason = 'new_field'
        AND variant_id IN ({v_ids})
    """)
    
    rejected = q_val(f"""
        SELECT COUNT(*) FROM field_provenance 
        WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4) 
        AND decision = 'rejected'
        AND variant_id IN ({v_ids})
    """)
    
    # Results from state
    res = state['results'].get(model_key)
    if isinstance(res, dict):
        status = 'SUCCESS'
        disc = res.get('discovered', 0)
        res_cnt = res.get('resolved', 0)
        unres = res.get('unresolved', 0)
        errors = 0
    else:
        status = str(res)
        disc = 0
        res_cnt = 0
        unres = 0
        errors = 1 if status == 'ERROR' else 0
        
    print(f"| {model_key} | {status} | {disc} | {res_cnt} | {unres} | {editions} | {new_fields} | {rejected} | {errors} |")

