import sqlite3
import shutil
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation

# Setup isolated DB
shutil.copy("knowledge_base/carrec_kb.db", "knowledge_base/test_aura.db")
db_path = "knowledge_base/test_aura.db"

pdf_path = "knowledge_base/sources/oem/hyundai/aura/latest/brochures/Aura_Brochure.pdf"

strategy = classify_layout(pdf_path, "hyundai", "aura")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute(pdf_path)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT id FROM source LIMIT 1")
source_id = c.fetchone()[0]

gen_id = resolve_oem_generation(conn, "Hyundai", "Aura", None)

process_oem_payload(conn, payloads, "hyundai", "aura", source_id, gen_id)

conn.commit()

c.execute("""
SELECT m.name, v.name, count(fp.id)
FROM field_provenance fp
JOIN variant v ON fp.variant_id = v.id
JOIN model m ON v.model_id = m.id
WHERE m.name = 'Aura'
GROUP BY v.name
""")
rows = c.fetchall()
for r in rows:
    print(f"Resolved Variant: {r[1]} - {r[2]} features mapped")
