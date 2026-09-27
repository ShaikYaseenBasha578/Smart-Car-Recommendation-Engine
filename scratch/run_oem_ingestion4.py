import sqlite3
import json
import shutil
import os
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation

db_prod = "knowledge_base/carrec_kb.db"
db_test = "scratch/phase6_dryrun.sqlite"
if os.path.exists(db_test): os.remove(db_test)
shutil.copy(db_prod, db_test)

conn = sqlite3.connect(db_test)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id FROM model WHERE name='Swift'")
swift_model_id = cur.fetchone()[0]

cur.execute('''
    INSERT INTO generation (model_id, name, start_year, verification_status)
    VALUES (?, '4th Generation', 2024, 'verified')
''', (swift_model_id,))
gen4_id = cur.lastrowid

cur.execute('''
    INSERT INTO generation (model_id, name, start_year, verification_status)
    VALUES (?, '5th Generation', 2029, 'verified')
''', (swift_model_id,))
conn.commit()

cur.execute("UPDATE variant SET generation_id=? WHERE model_id=?", (gen4_id, swift_model_id))
conn.commit()

pinned_gen_id = resolve_oem_generation(conn, 'maruti suzuki', 'swift', 2024)
print(f"Explicitly pinned generation ID: {pinned_gen_id} (Expected: {gen4_id})")

cur.execute("INSERT OR IGNORE INTO source (name, source_type, authority_tier) VALUES ('oem', 'oem', 1)")
cur.execute("SELECT id FROM source WHERE name='oem'")
source_id = cur.fetchone()[0]

with open("scratch/swift_dry_run_extracted.json", "r") as f:
    payload = json.load(f)

print("--- FIRST RUN ---")
results = process_oem_payload(conn, payload, 'maruti-suzuki', 'swift', source_id, pinned_gen_id)
print("Ingestion Results:", results)

cur.execute('SELECT COUNT(*) FROM source_observation so JOIN variant v ON so.resolved_variant_id = v.id WHERE so.source_id = ? AND v.generation_id != ?', (source_id, pinned_gen_id))
wrong_gen = cur.fetchone()[0]
print("Observations attached to wrong generation:", wrong_gen)

print("--- IDEMPOTENCY RUN ---")
results2 = process_oem_payload(conn, payload, 'maruti-suzuki', 'swift', source_id, pinned_gen_id)
print("Idempotency Results:", results2)
conn.commit()
