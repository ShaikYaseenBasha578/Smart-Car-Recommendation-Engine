import os
import json
import sqlite3
import shutil
import traceback
from collections import defaultdict

from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation

PROD_DB = "knowledge_base/carrec_kb.db"

def capture_db_state(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    state = {'counts': {}, 'max_ids': {}}
    for t in ['manufacturer', 'model', 'generation', 'variant', 'source_observation', 'field_provenance']:
        c.execute(f"SELECT COUNT(*) FROM {t}")
        state['counts'][t] = c.fetchone()[0]
        c.execute(f"SELECT MAX(id) FROM {t}")
        state['max_ids'][t] = c.fetchone()[0] or 0
        
    # Also capture all field_provenance rows for diffing
    c.execute("SELECT * FROM field_provenance")
    state['prov_rows'] = {row['id']: dict(row) for row in c.fetchall()}
    conn.close()
    return state

def run_ingestion_pass(db_path):
    with open("knowledge_base/sources/oem/brochure_manifest.json", 'r') as f:
        manifest = json.load(f)
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None # Autocommit off
    
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
            conn.execute('ROLLBACK')
            if "Generation Pinning Failed" in str(e):
                stats['RESOLUTION_FAILURE'].append(key)
            else:
                stats['DB_FAILURE'].append(key)
                print(f"DB_FAILURE on {make} {model}: {e}")
                
    conn.close()
    return stats

def main():
    shadow_db = "scratch/isolated_shadow_kb.db"
    shutil.copy2(PROD_DB, shadow_db)
    
    print("--- SHADOW INGESTION RUN 1 ---")
    state_before = capture_db_state(shadow_db)
    stats1 = run_ingestion_pass(shadow_db)
    state_after = capture_db_state(shadow_db)
    
    print("Diffs after Run 1:")
    for t in state_before['counts']:
        delta = state_after['counts'][t] - state_before['counts'][t]
        print(f"  {t}: {delta:+d}")
        
    # Analyze exactly what was added
    new_prov_ids = set(state_after['prov_rows'].keys()) - set(state_before['prov_rows'].keys())
    print(f"\nNew provenance records: {len(new_prov_ids)}")
    accepted = 0
    rejected = 0
    for pid in new_prov_ids:
        r = state_after['prov_rows'][pid]
        if r['decision'] == 'accepted': accepted += 1
        elif r['decision'] == 'rejected': rejected += 1
    print(f"  Accepted (Canonical mutated): {accepted}")
    print(f"  Rejected (Conflict): {rejected}")
    
    print("\nRun 1 Classification Stats:")
    for k, v in stats1.items():
        if k != 'total_attempted':
            print(f"  {k}: {len(v)}")
            
    print("\n--- SHADOW INGESTION RUN 2 (IDEMPOTENCY) ---")
    state_before_run2 = capture_db_state(shadow_db)
    stats2 = run_ingestion_pass(shadow_db)
    state_after_run2 = capture_db_state(shadow_db)
    
    print("Diffs after Run 2:")
    idempotency_failed = False
    for t in state_before_run2['counts']:
        delta = state_after_run2['counts'][t] - state_before_run2['counts'][t]
        print(f"  {t}: {delta:+d}")
        if delta != 0:
            idempotency_failed = True
            
    if idempotency_failed:
        print("\nIDEMPOTENCY TEST: FAILED")
    else:
        print("\nIDEMPOTENCY TEST: PASSED")

if __name__ == '__main__':
    main()
