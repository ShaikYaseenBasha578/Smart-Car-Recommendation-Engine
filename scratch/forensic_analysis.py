import sqlite3
import os

prod_db = "knowledge_base/carrec_kb.db"
backup_db = "scratch/carrec_kb_production_backup.db"

tables_to_check = ['manufacturer', 'model', 'generation', 'variant', 'source_observation', 'field_provenance']

def get_row_counts(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    counts = {}
    for t in tables_to_check:
        try:
            c.execute(f"SELECT COUNT(*) FROM {t}")
            counts[t] = c.fetchone()[0]
        except Exception as e:
            counts[t] = f"Error: {e}"
    conn.close()
    return counts

def get_max_ids(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    max_ids = {}
    for t in tables_to_check:
        try:
            c.execute(f"SELECT MAX(id) FROM {t}")
            max_ids[t] = c.fetchone()[0]
        except Exception:
            max_ids[t] = None
    conn.close()
    return max_ids

pre_counts = get_row_counts(backup_db)
post_counts = get_row_counts(prod_db)
pre_max_ids = get_max_ids(backup_db)
post_max_ids = get_max_ids(prod_db)

print("ROW COUNTS")
for t in tables_to_check:
    print(f"{t}: PRE={pre_counts[t]}, POST={post_counts[t]}, DELTA={post_counts[t] - pre_counts[t]}")

print("\nMAX IDs")
for t in tables_to_check:
    print(f"{t}: PRE={pre_max_ids[t]}, POST={post_max_ids[t]}")

# Let's inspect the exact new rows in source_observation and field_provenance
conn = sqlite3.connect(prod_db)
conn.row_factory = sqlite3.Row
c = conn.cursor()

new_obs = 0
if pre_max_ids['source_observation'] is not None:
    c.execute("SELECT * FROM source_observation WHERE id > ?", (pre_max_ids['source_observation'],))
    new_obs_rows = c.fetchall()
    new_obs = len(new_obs_rows)
    print(f"\nNew source_observations: {new_obs}")

new_prov = 0
if pre_max_ids['field_provenance'] is not None:
    c.execute("SELECT * FROM field_provenance WHERE id > ?", (pre_max_ids['field_provenance'],))
    new_prov_rows = c.fetchall()
    new_prov = len(new_prov_rows)
    print(f"New field_provenance rows: {new_prov}")
    for row in new_prov_rows:
        print(f"  ID {row['id']}: Variant {row['variant_id']}, Field {row['field_name']}, Val '{row['accepted_value']}', Decision {row['decision']}")
conn.close()

