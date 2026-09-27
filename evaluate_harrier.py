import sqlite3
import json

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get all CarWale observations for Harrier
c.execute("""
    SELECT o.raw_name, o.source_url, o.resolution_status, o.resolved_variant_id, 
           v.name as canonical_name, v.base_variant_id, v.edition_classification,
           bv.name as base_name
    FROM source_observation o
    LEFT JOIN variant v ON o.resolved_variant_id = v.id
    LEFT JOIN variant bv ON v.base_variant_id = bv.id
    WHERE o.source_id = 4 AND o.source_url LIKE '%harrier%'
""")

rows = c.fetchall()
print("| CarWale Raw Name | URL | Proposed Base Variant | Resolution Result | Classification | Disposition |")
print("|---|---|---|---|---|---|")
for r in rows:
    raw = r['raw_name']
    url = r['source_url']
    res = r['resolution_status']
    canon = r['canonical_name']
    base = r['base_name']
    c_id = r['resolved_variant_id']
    cls = r['edition_classification']
    
    proposed_base = base if base else (canon if canon else "None")
    if res == 'unresolvable':
        proposed_base = "None"
        cls = "OUTSIDE_CANONICAL_SCOPE"
    elif cls is None:
        cls = "BASE_VARIANT"
        
    disp = "Stored" if res != 'unresolvable' else "Rejected"
    
    # Let's check actual differences if it's an edition
    diffs = "None"
    if cls in ['FEATURE_OR_SPEC_DIFFERENCE', 'NO_MATERIAL_DIFFERENCE'] and c_id:
        c.execute("SELECT field_name, accepted_value FROM field_provenance WHERE variant_id = ?", (c_id,))
        prov = c.fetchall()
        if prov:
            diffs = ", ".join([f"{p['field_name']}={p['accepted_value']}" for p in prov])
            
    print(f"| {raw} | {url} | {proposed_base} | {res} | {cls} | {disp} |")
    
