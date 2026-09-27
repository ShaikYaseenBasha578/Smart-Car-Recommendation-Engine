with open('knowledge_base/ingestion/carwale/ingest_carwale.py', 'r') as f:
    code = f.read()

# I need to fix the call to update_canonical which is currently hardcoded with 'resolved'
code = code.replace("'resolved', normalized", "match_status, normalized")
# wait, actually, let me just write it carefully using re
import re
code = re.sub(
    r"update_canonical\(\s*conn,\s*target_variant_id,\s*CARWALE_SOURCE_ID,\s*v_url,\s*v_name,\s*payload_dump,\s*'resolved',\s*normalized,\s*base_variant_id\s*\)",
    r"update_canonical(conn, target_variant_id, CARWALE_SOURCE_ID, v_url, v_name, payload_dump, match_status, normalized, base_variant_id)",
    code
)

with open('knowledge_base/ingestion/carwale/ingest_carwale.py', 'w') as f:
    f.write(code)
