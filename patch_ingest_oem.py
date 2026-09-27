with open("knowledge_base/ingestion/oem/ingest_oem.py", "r") as f:
    code = f.read()

new_logic = """
def resolve_oem_generation(conn, make_slug, model_slug, start_year):
    '''
    Strictly resolves exactly ONE generation for OEM ingestion.
    Fails closed if 0 or >1 matches are found to prevent ambiguity.
    '''
    cur = conn.cursor()
    cur.execute('''
        SELECT g.id, g.name 
        FROM generation g
        JOIN model m ON g.model_id = m.id
        JOIN make mk ON m.make_id = mk.id
        WHERE mk.slug = ? AND m.slug = ? AND g.start_year = ?
    ''', (make_slug, model_slug, start_year))
    
    rows = cur.fetchall()
    
    if len(rows) == 0:
        raise ValueError(f"Generation Pinning Failed: 0 matches found for {make_slug} {model_slug} starting {start_year}.")
    
    if len(rows) > 1:
        raise ValueError(f"Generation Pinning Failed: Ambiguous lookup. {len(rows)} matches found for {make_slug} {model_slug} starting {start_year}.")
        
    return rows[0]['id']
"""

code += new_logic

with open("knowledge_base/ingestion/oem/ingest_oem.py", "w") as f:
    f.write(code)
