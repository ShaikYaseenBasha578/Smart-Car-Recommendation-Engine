import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)))))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import sqlite3
import json

conn = open_kb(KB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

def get_count(table, where=""):
    c.execute(f"SELECT COUNT(*) as c FROM {table} {where}")
    return c.fetchone()['c']

stats = {
    'manufacturer': get_count('manufacturer'),
    'model': get_count('model'),
    'generation': get_count('generation'),
    'powertrain': get_count('powertrain'),
    'base_variants': get_count('variant', 'WHERE edition_classification IS NULL'),
    'edition_variants': get_count('variant', 'WHERE edition_classification IS NOT NULL'),
    'source': get_count('source'),
    'source_observation': get_count('source_observation'),
    'field_provenance': get_count('field_provenance'),
    'variant_alias': get_count('variant_alias')
}

with open('knowledge_base/carwale_snapshot_before.json', 'w') as f:
    json.dump(stats, f, indent=2)

print("Pre-crawl stats:", json.dumps(stats, indent=2))
