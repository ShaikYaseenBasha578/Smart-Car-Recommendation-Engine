with open('knowledge_base/ingestion/carwale/ingest_carwale.py', 'r') as f:
    code = f.read()

import re
code = re.sub(
    r"update_canonical\(\s*conn,\s*target_variant_id,\s*CARWALE_SOURCE_ID,\s*v_url,\s*v_name,\s*payload_dump,\s*match_status,\s*normalized\s*\)",
    r"update_canonical(conn, target_variant_id, CARWALE_SOURCE_ID, v_url, v_name, payload_dump, match_status, normalized, base_variant_id)",
    code
)

with open('knowledge_base/ingestion/carwale/ingest_carwale.py', 'w') as f:
    f.write(code)
