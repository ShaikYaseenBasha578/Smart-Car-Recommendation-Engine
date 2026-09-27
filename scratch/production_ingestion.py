import json
import sqlite3
import time
import sys
import os

from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation

def run_production():
    print("STARTING TRANSACTIONAL PRODUCTION INGESTION...")
    manifest_path = "knowledge_base/sources/oem/brochure_manifest.json"
    prod_db = "knowledge_base/carrec_kb.db"
    
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
        
    conn = sqlite3.connect(prod_db)
    conn.row_factory = sqlite3.Row
    
    # Enable explicit transactions
    conn.isolation_level = None
    conn.execute('BEGIN TRANSACTION')
    
    total_extracted = 0
    total_resolved = 0
    total_unresolved = 0
    
    try:
        start_time = time.time()
        for key, info in manifest.items():
            artifact_path = info.get('artifact_path')
            make = info['manufacturer']
            model = info['model']
            
            if not artifact_path or not os.path.exists(artifact_path):
                continue
                
            sig = profile_pdf(artifact_path)
            if sig.is_cid_corrupted or not (sig.text_pages > 0):
                continue
                
            try:
                strategy = classify_layout(artifact_path, make, model)
                extractor = OEMBrochureExtractor(strategy)
                payloads = extractor.execute(artifact_path)
                total_extracted += len(payloads)
            except Exception:
                continue
                
            if not payloads:
                continue
                
            try:
                gen_id = resolve_oem_generation(conn, make, model, None)
                make_slug = make.lower().replace(" ", "-")
                model_slug = model.lower().replace(" ", "-")
                res = process_oem_payload(conn, payloads, make_slug, model_slug, 1, gen_id)
                total_resolved += res['resolved']
                total_unresolved += res['unresolved']
            except Exception as e:
                pass
                
        # If we got here, everything processed without a fatal crash
        conn.execute('COMMIT')
        print(f"TRANSACTION COMMITTED. Extracted: {total_extracted}, Resolved: {total_resolved}, Unresolved: {total_unresolved}")
    except Exception as e:
        conn.execute('ROLLBACK')
        print(f"FATAL ERROR, TRANSACTION ROLLED BACK: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    run_production()
