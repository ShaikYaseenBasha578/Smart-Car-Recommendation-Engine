def patch():
    with open('knowledge_base/ingestion/oem/ingest_oem.py', 'r') as f:
        text = f.read()
    
    text = text.replace("rows[0]['id']", "rows[0][0]")
    
    with open('knowledge_base/ingestion/oem/ingest_oem.py', 'w') as f:
        f.write(text)
patch()
