import sqlite3
from knowledge_base.ingestion.common.resolver import resolve_variant

conn = sqlite3.connect("scratch/phase6_swift_dry_run.sqlite")
conn.row_factory = sqlite3.Row
print(resolve_variant(conn, 'maruti-suzuki', 'swift', 'LXi Petrol Manual', 'lxi-petrol-manual', 'Petrol', 'MT', 1197, None, generation_id=23, active_only=False))
