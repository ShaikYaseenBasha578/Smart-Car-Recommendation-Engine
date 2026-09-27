import sqlite3
import json

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

def q(query):
    c.execute(query)
    return c.fetchall()

print("--- Source 3 (V3Cars) Unresolved ---")
v3_unresolved = q("SELECT id, raw_name, resolved_variant_id, resolution_status FROM source_observation WHERE source_id=3 AND resolution_status != 'resolved'")
print(f"Count: {len(v3_unresolved)}")
for i, row in enumerate(v3_unresolved[:5]):
    print(dict(row))

print("\n--- Source 4 (CarWale) Resolved ---")
cw_resolved = q("SELECT id, raw_name, resolved_variant_id, resolution_status FROM source_observation WHERE source_id=4 AND resolution_status = 'resolved'")
print(f"Count: {len(cw_resolved)}")

print("\n--- Transmission Values in Variant ---")
trans = q("SELECT transmission, COUNT(*) FROM variant GROUP BY transmission")
for t in trans:
    print(dict(t))

