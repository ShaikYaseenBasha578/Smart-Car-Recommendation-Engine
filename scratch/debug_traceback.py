from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields
import sqlite3
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"
strategy = classify_layout(pdf_path, "Maruti Suzuki", "Swift")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute(pdf_path)

print("Mapped fields:")
for p in payloads[:1]:
    mapped = map_oem_fields(p)
    print(mapped)

conn = sqlite3.connect("scratch/isolated_shadow_kb.db")
try:
    process_oem_payload(conn, payloads, "maruti-suzuki", "swift", 1, 35) # 35 is just a dummy gen_id for swift, let me check
except Exception as e:
    import traceback
    traceback.print_exc()
