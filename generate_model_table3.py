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

print("| Model | Discovered | Aborted | Failed Parse | Logged DB | Resolved | Unresolvable | Editions | New Fields | Rejected |")
print("|---|---|---|---|---|---|---|---|---|---|")

c.execute("SELECT id, name, manufacturer_id FROM model ORDER BY manufacturer_id, name")
models = c.fetchall()

for m in models:
    c.execute("SELECT name FROM manufacturer WHERE id=?", (m[2],))
    make_name = c.fetchone()[0]
    canonical_slug = m[1].lower().replace(' ', '-')
    make_slug = make_name.lower().replace(' ', '-')
    model_key = f"{make_slug}_{canonical_slug}"
    
    # Check if this model aborts on DB lookup
    c.execute("""
        SELECT m.id FROM model m
        JOIN manufacturer ma ON m.manufacturer_id = ma.id
        WHERE LOWER(ma.name) = ? AND LOWER(m.name) = ?
    """, (make_slug.lower().replace('-', ' '), canonical_slug.lower().replace('-', ' ')))
    aborted_lookup = not c.fetchone()
    
    # State stats
    res = state['results'].get(model_key, {})
    disc = res.get('discovered', 0) if isinstance(res, dict) else 0
    
    aborted = disc if aborted_lookup else 0
    
    # DB URL Logged
    url_pattern = f"%carwale.com/{make_slug}-cars/{canonical_slug}/%"
    logged_db = q_val("SELECT COUNT(*) FROM source_observation WHERE source_id=4 AND source_url LIKE ?", (url_pattern,))
    resolved_db = q_val("SELECT COUNT(*) FROM source_observation WHERE source_id=4 AND resolution_status='resolved' AND source_url LIKE ?", (url_pattern,))
    unres_db = q_val("SELECT COUNT(*) FROM source_observation WHERE source_id=4 AND resolution_status!='resolved' AND source_url LIKE ?", (url_pattern,))
    
    failed_parse = disc - aborted - logged_db
    
    editions = q_val(f"SELECT COUNT(*) FROM variant WHERE model_id={m[0]} AND edition_classification IS NOT NULL")
    
    new_fields = q_val(f"""
        SELECT COUNT(*) FROM field_provenance 
        WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4 AND source_url LIKE ?) 
        AND decision = 'accepted' AND decision_reason = 'new_field'
    """, (url_pattern,))
    
    rejected = q_val(f"""
        SELECT COUNT(*) FROM field_provenance 
        WHERE source_observation_id IN (SELECT id FROM source_observation WHERE source_id=4 AND source_url LIKE ?) 
        AND decision = 'rejected'
    """, (url_pattern,))
    
    print(f"| {model_key} | {disc} | {aborted} | {failed_parse} | {logged_db} | {resolved_db} | {unres_db} | {editions} | {new_fields} | {rejected} |")

