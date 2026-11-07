import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)))))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import sqlite3

conn = open_kb(KB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

def print_count(table):
    c.execute(f"SELECT COUNT(*) as cnt FROM {table}")
    print(f"{table.capitalize()} count: {c.fetchone()['cnt']}")

print_count("manufacturer")
print_count("model")
print_count("generation")
print_count("powertrain")
c.execute("SELECT COUNT(*) as cnt FROM variant WHERE edition_classification IS NULL")
print(f"Canonical Variants (Base): {c.fetchone()['cnt']}")
c.execute("SELECT COUNT(*) as cnt FROM variant WHERE edition_classification IS NOT NULL")
print(f"Editions (Variants): {c.fetchone()['cnt']}")
print_count("source")
print_count("source_observation")
print_count("field_provenance")
print_count("variant_alias")

# Duplicate check
c.execute("SELECT name, COUNT(*) as c FROM variant GROUP BY name HAVING c > 1")
dupes = c.fetchall()
print(f"Duplicate variant names: {len(dupes)}")
for d in dupes: print(f" - {d['name']}")

