with open('knowledge_base/ingestion/carwale/ingest_carwale.py', 'r') as f:
    code = f.read()

code = code.replace("for i, v in enumerate(versions[:10]):", "for i, v in enumerate(versions):")

with open('knowledge_base/ingestion/carwale/ingest_carwale.py', 'w') as f:
    f.write(code)
