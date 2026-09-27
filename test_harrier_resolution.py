from knowledge_base.ingestion.common.resolver import resolve_variant
import sqlite3
conn = sqlite3.connect('knowledge_base/carrec_kb.db')
conn.row_factory = sqlite3.Row
print(resolve_variant(conn, 'tata', 'harrier', 'Pure X Petrol 1.5L Turbo Manual Dark Edition', 'pure-x-petrol-15l-turbo-manual-dark-edition', 'Petrol', 'Manual', 1498, None))
