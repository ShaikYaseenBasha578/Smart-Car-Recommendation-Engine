import os

for script in ['knowledge_base/ingestion/carwale/ingest_carwale.py', 'knowledge_base/ingestion/v3cars/ingest_v3cars.py', 'knowledge_base/ingestion/91wheels/ingest_91wheels.py']:
    with open(script, 'r') as f:
        code = f.read()
        
    code = code.replace("if not target_variant_id:", "if not target_variant_id and match_status != 'edition_candidate':")
    
    with open(script, 'w') as f:
        f.write(code)
