import sqlite3

conn = sqlite3.connect('knowledge_base/carrec_kb.db')
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

