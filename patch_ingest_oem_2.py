import re
with open("knowledge_base/ingestion/oem/ingest_oem.py", "r") as f:
    code = f.read()

new_logic = """
def resolve_oem_generation(conn, make_name, model_name, start_year):
    '''
    Strictly resolves exactly ONE generation for OEM ingestion.
    Fails closed if 0 or >1 matches are found to prevent ambiguity.
    '''
    cur = conn.cursor()
    # Normalize strings for matching
    make_clean = str(make_name).lower().replace('-', ' ').strip()
    model_clean = str(model_name).lower().replace('-', ' ').strip()
    
    cur.execute('''
        SELECT g.id, g.name 
        FROM generation g
        JOIN model m ON g.model_id = m.id
        JOIN manufacturer mk ON m.manufacturer_id = mk.id
        WHERE LOWER(mk.name) = ? AND LOWER(m.name) = ? AND g.start_year = ?
    ''', (make_clean, model_clean, start_year))
    
    rows = cur.fetchall()
    
    if len(rows) == 0:
        raise ValueError(f"Generation Pinning Failed: 0 matches found for {make_clean} {model_clean} starting {start_year}.")
    
    if len(rows) > 1:
        raise ValueError(f"Generation Pinning Failed: Ambiguous lookup. {len(rows)} matches found for {make_clean} {model_clean} starting {start_year}.")
        
    return rows[0]['id']
"""

code = re.sub(r'def resolve_oem_generation.*?return rows\[0\]\[\'id\'\]', new_logic.strip(), code, flags=re.DOTALL)

with open("knowledge_base/ingestion/oem/ingest_oem.py", "w") as f:
    f.write(code)
