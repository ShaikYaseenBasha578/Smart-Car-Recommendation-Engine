import os
import json
import sqlite3
import traceback

from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation

PROD_DB = "knowledge_base/carrec_kb.db"

def get_snapshot(conn, tables):
    c = conn.cursor()
    snap = {}
    for t in tables:
        c.execute(f"SELECT * FROM {t}")
        snap[t] = {row['id']: dict(row) for row in c.fetchall()}
    return snap

def run_production_ingestion():
    with open("knowledge_base/sources/oem/brochure_manifest.json", 'r') as f:
        manifest = json.load(f)
        
    conn = sqlite3.connect(PROD_DB)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None # Autocommit off
    
    tables = ['manufacturer', 'model', 'generation', 'variant', 'powertrain', 'source_observation', 'field_provenance']
    snap_before = get_snapshot(conn, tables)
    
    stats = {
        'total_attempted': 0, 'GENERIC_SUCCESS': [], 'GENERIC_PARTIAL': [],
        'EXTRACTION_FAILURE': [], 'RESOLUTION_FAILURE': [], 'PDF_TEXT_FAILURE': [],
        'CLASSIFICATION_UNKNOWN': [], 'DB_FAILURE': []
    }
    
    for key, info in manifest.items():
        stats['total_attempted'] += 1
        artifact_path = info.get('artifact_path')
        make = info['manufacturer']
        model = info['model']
        
        if not artifact_path or not os.path.exists(artifact_path):
            stats['PDF_TEXT_FAILURE'].append(key)
            continue
            
        try:
            sig = profile_pdf(artifact_path)
            if sig.is_cid_corrupted or not (sig.text_pages > 0):
                stats['PDF_TEXT_FAILURE'].append(key)
                continue
        except Exception:
            stats['PDF_TEXT_FAILURE'].append(key)
            continue
            
        try:
            strategy = classify_layout(artifact_path, make, model)
        except Exception:
            stats['CLASSIFICATION_UNKNOWN'].append(key)
            continue
            
        try:
            extractor = OEMBrochureExtractor(strategy)
            payloads = extractor.execute(artifact_path)
            if not payloads:
                stats['EXTRACTION_FAILURE'].append(key)
                continue
        except Exception:
            stats['EXTRACTION_FAILURE'].append(key)
            continue
            
        try:
            conn.execute('BEGIN TRANSACTION')
            gen_id = resolve_oem_generation(conn, make, model, None)
            make_slug = make.lower().replace(" ", "-")
            model_slug = model.lower().replace(" ", "-")
            res = process_oem_payload(conn, payloads, make_slug, model_slug, 1, gen_id)
            conn.execute('COMMIT')
            
            if res['resolved'] == 0:
                stats['RESOLUTION_FAILURE'].append(key)
            elif res['resolved'] < len(payloads):
                stats['GENERIC_PARTIAL'].append(key)
            else:
                stats['GENERIC_SUCCESS'].append(key)
                
        except Exception as e:
            try:
                conn.execute('ROLLBACK')
            except:
                pass
            if "Generation Pinning Failed" in str(e):
                stats['RESOLUTION_FAILURE'].append(key)
            else:
                stats['DB_FAILURE'].append(key)
                print(f"DB_FAILURE on {make} {model}: {e}")
                
    snap_after = get_snapshot(conn, tables)
    conn.close()
    
    print("--- PRODUCTION INGESTION COMPLETE ---")
    for t in tables:
        added = len(snap_after[t]) - len(snap_before[t])
        print(f"Table {t} net row delta: {added}")
        
    print("\nExtraction/Classification Stats:")
    for k, v in stats.items():
        if k != 'total_attempted':
            print(f"  {k}: {len(v)}")

if __name__ == '__main__':
    run_production_ingestion()
