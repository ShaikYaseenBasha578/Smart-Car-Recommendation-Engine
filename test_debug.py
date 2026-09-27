import sqlite3
import json
from knowledge_base.ingestion.common.updater import update_canonical
from knowledge_base.ingestion.common.resolver import resolve_variant

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("DELETE FROM source_observation WHERE raw_name = 'Pure X Petrol 1.5L Turbo Manual Dark Edition'")
conn.commit()

t_id, status, base_id = resolve_variant(conn, 'tata', 'harrier', 'Pure X Petrol 1.5L Turbo Manual Dark Edition', 'pure-x-petrol-15l-turbo-manual-dark-edition', 'Petrol', 'Manual', 1498, None)
print(f"Resolver returned: {t_id}, {status}, {base_id}")

obs_id, updates = update_canonical(conn, t_id, 4, 'http', 'Pure X Petrol 1.5L Turbo Manual Dark Edition', {}, status, {'sunroof': 1}, base_id)
print(f"Updater returned: {obs_id}, {updates}")

c.execute("SELECT resolution_status, resolved_variant_id FROM source_observation WHERE id = ?", (obs_id,))
print("Observation in DB:", dict(c.fetchone()))

