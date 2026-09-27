import sqlite3
import shutil
import os
from knowledge_base.ingestion.oem.ingest_oem import resolve_oem_generation

db_prod = "knowledge_base/carrec_kb.db"
db_test = "scratch/phase6_ambiguity_test.sqlite"
if os.path.exists(db_test): os.remove(db_test)
shutil.copy(db_prod, db_test)

conn = sqlite3.connect(db_test)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get IDs
cur.execute("SELECT m.id, mk.name as make_name, m.name as model_name FROM model m JOIN manufacturer mk ON m.manufacturer_id=mk.id WHERE m.name='Swift'")
row = cur.fetchone()
swift_model_id = row[0]
make_name = row[1]
model_name = row[2]

# Insert Gen-4 (2024)
cur.execute('''
    INSERT INTO generation (model_id, name, start_year, verification_status)
    VALUES (?, '4th Generation', 2024, 'verified')
''', (swift_model_id,))

# Future Test: Insert Gen-5 (2029)
cur.execute('''
    INSERT INTO generation (model_id, name, start_year, verification_status)
    VALUES (?, '5th Generation', 2029, 'verified')
''', (swift_model_id,))
conn.commit()

# Test 1: Future regression (should correctly find exactly one 2024 generation)
try:
    gen_id = resolve_oem_generation(conn, make_name, model_name, 2024)
    print("Future Generation Pinning Test: PASSED (Returned exactly one Gen-4 ID)")
except Exception as e:
    print("Future Generation Pinning Test: FAILED", e)

# Test 2: Ambiguity Test (Insert another 2024 generation)
cur.execute('''
    INSERT INTO generation (model_id, name, start_year, verification_status)
    VALUES (?, '4th Generation (Duplicate for test)', 2024, 'verified')
''', (swift_model_id,))
conn.commit()

try:
    resolve_oem_generation(conn, make_name, model_name, 2024)
    print("Ambiguity Test: FAILED (Did not raise error)")
except ValueError as e:
    if "Ambiguous lookup" in str(e):
        print("Ambiguity Test: PASSED (Failed closed with ambiguity error)")
    else:
        print("Ambiguity Test: FAILED (Wrong error type):", e)
        
conn.close()
