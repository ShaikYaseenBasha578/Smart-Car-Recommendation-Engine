import re

for script in ['knowledge_base/ingestion/carwale/ingest_carwale.py', 'knowledge_base/ingestion/v3cars/ingest_v3cars.py', 'knowledge_base/ingestion/91wheels/ingest_91wheels.py']:
    with open(script, 'r') as f:
        code = f.read()
        
    code = code.replace("update_canonical(conn, target_variant_id, CARWALE_SOURCE_ID, v_url, v_name, payload_dump, 'resolved', normalized, base_variant_id)", "update_canonical(conn, target_variant_id, CARWALE_SOURCE_ID, v_url, v_name, payload_dump, match_status, normalized, base_variant_id)")
    
    with open(script, 'w') as f:
        f.write(code)
