import sqlite3
import shutil
import os
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.strategies.hyundai_creta_2024 import HyundaiCreta2024Strategy

db_prod = "knowledge_base/carrec_kb.db"
db_test = "scratch/phase6_creta_dryrun.sqlite"
if os.path.exists(db_test): os.remove(db_test)
shutil.copy(db_prod, db_test)

conn = sqlite3.connect(db_test)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id FROM model WHERE name='Creta'")
creta_model_id = cur.fetchone()[0]

cur.execute('''
    INSERT INTO generation (model_id, name, start_year, verification_status)
    VALUES (?, 'Gen 2 Facelift', 2024, 'verified')
''', (creta_model_id,))
gen_id = cur.lastrowid
conn.commit()

# Move the Creta variants to this Gen ID so they can be matched
cur.execute("UPDATE variant SET generation_id=? WHERE model_id=?", (gen_id, creta_model_id))
conn.commit()

cur.execute("INSERT OR IGNORE INTO source (name, source_type, authority_tier) VALUES ('oem', 'oem', 1)")
cur.execute("SELECT id FROM source WHERE name='oem'")
source_id = cur.fetchone()[0]

strategy = HyundaiCreta2024Strategy()
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute("knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf")

print("--- CRETA FIRST RUN ---")
results = process_oem_payload(conn, payloads, 'hyundai', 'creta', source_id, gen_id)
print("Ingestion Results:", results)
conn.commit()

print("--- CRETA IDEMPOTENCY RUN ---")
results2 = process_oem_payload(conn, payloads, 'hyundai', 'creta', source_id, gen_id)
print("Idempotency Results:", results2)
