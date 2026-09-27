with open('knowledge_base/ingestion/common/updater.py', 'r') as f:
    code = f.read()

code = code.replace("""    # Use v_effective_variant to get the inherited truth, so we don't treat inherited values as overrides!
    cur.execute('SELECT * FROM v_effective_variant WHERE id = ?', (variant_id,))
    v_row = cur.fetchone()
    if not v_row: 
        # Fallback to variant table if view is somehow missing
        cur.execute('SELECT * FROM variant WHERE id = ?', (variant_id,))
        v_row = cur.fetchone()""", """    # Use v_effective_variant to get the inherited truth, so we don't treat inherited values as overrides!
    try:
        cur.execute('SELECT * FROM v_effective_variant WHERE id = ?', (variant_id,))
        v_row = cur.fetchone()
    except sqlite3.OperationalError:
        cur.execute('SELECT * FROM variant WHERE id = ?', (variant_id,))
        v_row = cur.fetchone()""")

with open('knowledge_base/ingestion/common/updater.py', 'w') as f:
    f.write(code)
