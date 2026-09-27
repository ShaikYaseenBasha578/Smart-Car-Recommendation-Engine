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

print("| Model | Discovered Slugs | Fetched (Logged DB) | Resolved | Unresolvable (Scope) | Failed Fetch/Parse | Aborted (DB Lookup) | Editions | New Fields | Rejected |")
print("|---|---|---|---|---|---|---|---|---|---|")

c.execute("SELECT id, name, manufacturer_id FROM model")
models = c.fetchall()

tot_disc = tot_fetched = tot_res = tot_unres = tot_failed = tot_aborted = tot_editions = tot_new = tot_rej = 0

for m in models:
    c.execute("SELECT name FROM manufacturer WHERE id=?", (m[2],))
    make_name = c.fetchone()[0]
    canonical_slug = m[1].lower().replace(' ', '-')
    make_slug = make_name.lower().replace(' ', '-')
    model_key = f"{make_slug}_{canonical_slug}"
    
    # DB Stats
    v_ids = f"SELECT id FROM variant WHERE model_id={m[0]}"
    
    # URL Logged
    # We can match source_url to identify models, or match resolved_variant_id
    # But for unresolved, resolved_variant_id is NULL!
    # So we must match source_url!
    cw_model_slug = canonical_slug
    url_pattern = f"%carwale.com/{make_slug}-cars/{cw_model_slug}/%"
    fetched_db = q_val("SELECT COUNT(*) FROM source_observation WHERE source_id=4 AND source_url LIKE ?", (url_pattern,))
    
    resolved_db = q_val("SELECT COUNT(*) FROM source_observation WHERE source_id=4 AND resolution_status='resolved' AND source_url LIKE ?", (url_pattern,))
    unres_db = q_val("SELECT COUNT(*) FROM source_observation WHERE source_id=4 AND resolution_status!='resolved' AND source_url LIKE ?", (url_pattern,))
    
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
    
    # State stats
    res = state['results'].get(model_key, {})
    if isinstance(res, dict):
        disc = res.get('discovered', 0)
        # Aborted if it returned stats but fetched 0 when disc > 0
        aborted = disc if (fetched_db == 0 and disc > 0) else 0
        failed = disc - fetched_db - aborted if disc >= fetched_db else 0
    else:
        disc = 0
        aborted = 0
        failed = 0
        
    print(f"| {model_key} | {disc} | {fetched_db} | {resolved_db} | {unres_db} | {failed} | {aborted} | {editions} | {new_fields} | {rejected} |")
    
    tot_disc += disc
    tot_fetched += fetched_db
    tot_res += resolved_db
    tot_unres += unres_db
    tot_failed += failed
    tot_aborted += aborted
    tot_editions += editions
    tot_new += new_fields
    tot_rej += rejected

print(f"| **TOTALS** | **{tot_disc}** | **{tot_fetched}** | **{tot_res}** | **{tot_unres}** | **{tot_failed}** | **{tot_aborted}** | **{tot_editions}** | **{tot_new}** | **{tot_rej}** |")

