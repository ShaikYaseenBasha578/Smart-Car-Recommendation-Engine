import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)), "..")))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import sys
import os
import sqlite3
sys.path.append(os.getcwd())
from knowledge_base.ingestion.common.resolver import resolve_variant

conn = open_kb(KB_PATH)
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
