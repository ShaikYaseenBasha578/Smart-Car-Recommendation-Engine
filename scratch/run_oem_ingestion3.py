import sqlite3
import json
import shutil
import os

db_prod = "knowledge_base/carrec_kb.db"
db_test = "scratch/phase6_dryrun.sqlite"
if os.path.exists(db_test): os.remove(db_test)
shutil.copy(db_prod, db_test)

conn = sqlite3.connect(db_test)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Update the database explicitly for the Dry Run environment
# The production database only has the V6 placeholder. We insert the Gen-4 generation.
cur.execute("SELECT id FROM model WHERE name='Swift'")
swift_model_id = cur.fetchone()[0]

cur.execute('''
    INSERT INTO generation (model_id, name, start_year, verification_status)
    VALUES (?, '4th Generation', 2024, 'verified')
''', (swift_model_id,))
gen4_id = cur.lastrowid

# Let's also insert a Gen-5 (future) to prove it pins correctly
cur.execute('''
    INSERT INTO generation (model_id, name, start_year, verification_status)
    VALUES (?, '5th Generation', 2029, 'verified')
''', (swift_model_id,))
gen5_id = cur.lastrowid
conn.commit()

# Update variants to belong to Gen 4 (since they were dumped in Gen 1 placeholder)
# Actually, the base variants currently in the DB belong to Gen 1 placeholder.
# If we change generation_id to gen4_id, resolver will find them!
cur.execute("UPDATE variant SET generation_id=? WHERE model_id=?", (gen4_id, swift_model_id))
conn.commit()

# --- EXPLICIT GENERATION RESOLUTION ---
target_year = 2024
cur.execute('''
    SELECT g.id 
    FROM generation g 
    JOIN model m ON g.model_id = m.id 
    WHERE m.name = 'Swift' AND g.start_year = ?
''', (target_year,))
row = cur.fetchone()
if not row:
    raise ValueError(f"CRITICAL: Intended generation for {target_year} could not be uniquely identified. Failing closed.")
pinned_gen_id = row['id']
print(f"Explicitly pinned generation ID: {pinned_gen_id}")

cur.execute("INSERT OR IGNORE INTO source (name, source_type, authority_tier) VALUES ('oem', 'oem', 1)")
cur.execute("SELECT id FROM source WHERE name='oem'")
source_id = cur.fetchone()[0]

with open("scratch/swift_dry_run_extracted.json", "r") as f:
    payload = json.load(f)

from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload
results = process_oem_payload(conn, payload, 'maruti-suzuki', 'swift', source_id, pinned_gen_id)
print("Ingestion Results:", results)

# Double check that we didn't touch gen5 variants
cur.execute("SELECT COUNT(*) FROM source_observation WHERE source_id=?", (source_id,))
print("Observations created:", cur.fetchone()[0])
conn.commit()

print("--- IDEMPOTENCY CHECK ---")
results2 = process_oem_payload(conn, payload, 'maruti-suzuki', 'swift', source_id, pinned_gen_id)
print("Second Run Results:", results2)
