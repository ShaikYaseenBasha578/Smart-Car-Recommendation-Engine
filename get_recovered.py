import sqlite3

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get canonical variants resolved by CW but NOT by V3Cars
c.execute("""
    SELECT v.id, v.name, v.is_discontinued, m.name as model_name, ma.name as make_name
    FROM variant v
    JOIN model m ON v.model_id = m.id
    JOIN manufacturer ma ON m.manufacturer_id = ma.id
    WHERE v.id IN (
        SELECT resolved_variant_id FROM source_observation 
        WHERE source_id=4 AND resolution_status='resolved'
    )
    AND v.id NOT IN (
        SELECT resolved_variant_id FROM source_observation 
        WHERE source_id=3 AND resolution_status='resolved' AND resolved_variant_id IS NOT NULL
    )
    ORDER BY ma.name, m.name, v.name
""")
recovered = c.fetchall()
print(f"Total Canonical Variants Resolved by CW but not V3Cars: {len(recovered)}")

# Break it down
discontinued = sum(1 for r in recovered if r['is_discontinued'])
active = len(recovered) - discontinued
print(f"Discontinued (Historical): {discontinued}")
print(f"Active (Current): {active}")

print("\nSample (First 10):")
for r in recovered[:10]:
    print(f"[{r['id']}] {r['make_name']} {r['model_name']} - {r['name']} (Discontinued: {r['is_discontinued']})")
    
