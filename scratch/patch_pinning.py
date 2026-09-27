def patch():
    with open('knowledge_base/ingestion/oem/ingest_oem.py', 'r') as f:
        text = f.read()
    
    old = """    cur.execute('''
        SELECT g.id, g.name 
        FROM generation g
        JOIN model m ON g.model_id = m.id
        JOIN manufacturer mk ON m.manufacturer_id = mk.id
        WHERE LOWER(mk.name) = ? AND LOWER(m.name) = ? AND g.start_year = ?
    ''', (make_clean, model_clean, start_year))"""
    
    new = """    if start_year is None:
        cur.execute('''
            SELECT g.id, g.name 
            FROM generation g
            JOIN model m ON g.model_id = m.id
            JOIN manufacturer mk ON m.manufacturer_id = mk.id
            WHERE LOWER(mk.name) = ? AND LOWER(m.name) = ?
        ''', (make_clean, model_clean))
    else:
        cur.execute('''
            SELECT g.id, g.name 
            FROM generation g
            JOIN model m ON g.model_id = m.id
            JOIN manufacturer mk ON m.manufacturer_id = mk.id
            WHERE LOWER(mk.name) = ? AND LOWER(m.name) = ? AND g.start_year = ?
        ''', (make_clean, model_clean, start_year))"""
        
    text = text.replace(old, new)
    
    with open('knowledge_base/ingestion/oem/ingest_oem.py', 'w') as f:
        f.write(text)
patch()
