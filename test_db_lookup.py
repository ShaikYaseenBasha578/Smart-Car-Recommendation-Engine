import sqlite3

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
c = conn.cursor()
c.execute("SELECT m.name as m_name, ma.name as ma_name, m.id FROM model m JOIN manufacturer ma ON m.manufacturer_id = ma.id")
models = c.fetchall()

aborted_models = []
for m_name, ma_name, m_id in models:
    canonical_model_slug = m_name.lower().replace(' ', '-')
    make_slug = ma_name.lower().replace(' ', '-')
    
    # Simulate ingest_carwale.py lookup:
    c.execute("""
        SELECT m.id FROM model m
        JOIN manufacturer ma ON m.manufacturer_id = ma.id
        WHERE LOWER(ma.name) = ? AND LOWER(m.name) = ?
    """, (make_slug.lower().replace('-', ' '), canonical_model_slug.lower().replace('-', ' ')))
    
    if not c.fetchone():
        aborted_models.append(f"{make_slug}_{canonical_model_slug}")

print("Aborted Models:", aborted_models)
