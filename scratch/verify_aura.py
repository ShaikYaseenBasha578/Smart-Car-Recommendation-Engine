import sqlite3

db_path = "knowledge_base/test_aura.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
SELECT m.name, v.name, count(fp.id)
FROM field_provenance fp
JOIN source_observation so ON fp.source_observation_id = so.id
JOIN source s ON so.source_id = s.id
JOIN variant v ON fp.variant_id = v.id
JOIN model m ON v.model_id = m.id
WHERE m.name = 'Aura' AND s.source_type = 'OEM_BROCHURE'
GROUP BY v.name
""")
rows = c.fetchall()
for r in rows:
    print(f"Resolved Variant: {r[1]} - {r[2]} OEM features mapped")
