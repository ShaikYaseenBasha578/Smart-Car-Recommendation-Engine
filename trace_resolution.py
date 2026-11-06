import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)))))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
from knowledge_base.ingestion.common.resolver import resolve_variant
import sqlite3
conn = open_kb(KB_PATH)
conn.row_factory = sqlite3.Row
print(resolve_variant(conn, 'tata', 'harrier', 'Pure X Petrol 1.5L Turbo Manual Dark Edition', 'pure-x-petrol-15l-turbo-manual-dark-edition', 'Petrol', 'Manual', 1498, None))
