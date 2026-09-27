import sys
import os
import sqlite3
sys.path.append(os.getcwd())
from knowledge_base.ingestion.common.resolver import resolve_variant

conn = sqlite3.connect("knowledge_base/carrec_kb.db")
conn.row_factory = sqlite3.Row
v_id, status, cand = resolve_variant(
    conn, "maruti-suzuki", "fronx", "Sigma", "sigma", 
    "CNG", "Manual", None, None, 
    generation_id=None, active_only=False, source_name='oem',
    engine_name="1.2L", edition=None
)
print("ID:", v_id)
print("Status:", status)
print("Cand:", cand)
