import sqlite3
import shutil
import os
import json
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

db_prod = "knowledge_base/carrec_kb.db"
db_test = "scratch/phase6_family_dryrun.sqlite"

def run_extraction(make, model, pdf_path, gen_year, gen_name=None):
    print(f"--- Processing {make} {model} ---")
    try:
        strategy = classify_layout(make, model)
        print(f"Assigned Strategy: {strategy.__class__.__name__}")
        
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(pdf_path)
        print(f"Configurations extracted: {len(payloads)}")
        
        if os.path.exists(db_test): os.remove(db_test)
        shutil.copy(db_prod, db_test)
        
        conn = sqlite3.connect(db_test)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM model WHERE name=? COLLATE NOCASE", (model,))
        model_id = cur.fetchone()[0]
        
        # Determine Gen ID
        if gen_name:
            cur.execute("INSERT INTO generation (model_id, name, start_year, verification_status) VALUES (?, ?, ?, 'verified')", (model_id, gen_name, gen_year))
            gen_id = cur.lastrowid
            cur.execute("UPDATE variant SET generation_id=? WHERE model_id=?", (gen_id, model_id))
            conn.commit()
        else:
            gen_id = resolve_oem_generation(conn, make, model, gen_year)
            
        cur.execute("INSERT OR IGNORE INTO source (name, source_type, authority_tier) VALUES ('oem', 'oem', 1)")
        cur.execute("SELECT id FROM source WHERE name='oem'")
        source_id = cur.fetchone()[0]
        conn.commit()
        
        res = process_oem_payload(conn, payloads, make.lower().replace(" ", "-"), model.lower().replace(" ", "-"), source_id, gen_id)
        print("Ingestion Results:", res)
        
    except Exception as e:
        print(f"Extraction failed: {e}")

run_extraction("Maruti Suzuki", "Swift", "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf", 2024, "Gen-4 (2024)")
run_extraction("Hyundai", "Creta", "knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf", 2024, "Gen 2 Facelift")
run_extraction("Maruti Suzuki", "Wagon_R", "knowledge_base/sources/oem/maruti_suzuki/wagon_r/latest/brochures/WagonR_Brochure.pdf", 2024)
run_extraction("Hyundai", "Grand i10 Nios", "knowledge_base/sources/oem/hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf", 2024)
run_extraction("Maruti Suzuki", "Fronx", "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf", 2024)
run_extraction("Maruti Suzuki", "Baleno", "knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf", 2024)
