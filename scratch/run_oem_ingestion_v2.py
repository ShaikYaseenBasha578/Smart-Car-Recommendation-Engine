import sqlite3
import json
import shutil
import os
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.strategies.swift_2024 import SwiftGen4VerticalStrategy

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

# Move placeholders to Gen 4 so resolver matches them
cur.execute("UPDATE variant SET generation_id=? WHERE model_id=?", (gen4_id, swift_model_id))
conn.commit()

pinned_gen_id = resolve_oem_generation(conn, 'maruti suzuki', 'swift', 2024)

cur.execute("INSERT OR IGNORE INTO source (name, source_type, authority_tier) VALUES ('oem', 'oem', 1)")
cur.execute("SELECT id FROM source WHERE name='oem'")
source_id = cur.fetchone()[0]
conn.commit()

# NEW EXTRACTION PIPELINE
strategy = SwiftGen4VerticalStrategy()
extractor = OEMBrochureExtractor(strategy)
payload = extractor.execute("knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf")

print("--- FIRST RUN ---")
results = process_oem_payload(conn, payload, 'maruti-suzuki', 'swift', source_id, pinned_gen_id)
print("Ingestion Results:", results)

print("--- IDEMPOTENCY RUN ---")
results2 = process_oem_payload(conn, payload, 'maruti-suzuki', 'swift', source_id, pinned_gen_id)
print("Idempotency Results:", results2)
conn.commit()
