import os
import json
import sqlite3
import shutil
import time
import argparse
from collections import defaultdict

from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation

def run_batch(models=None):
    manifest_path = "knowledge_base/sources/oem/brochure_manifest.json"
    prod_db = "knowledge_base/carrec_kb.db"
    isolated_db = "knowledge_base/isolated_batch_kb.db"
    
    if os.path.exists(isolated_db):
        os.remove(isolated_db)
    shutil.copy2(prod_db, isolated_db)
    
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
        
    conn = sqlite3.connect(isolated_db)
    conn.row_factory = sqlite3.Row
    
    results = {
        'total_attempted': 0,
        'GENERIC_SUCCESS': [],
        'GENERIC_PARTIAL': [],
        'EXTRACTION_FAILURE': [],
        'RESOLUTION_FAILURE': [],
        'PDF_TEXT_FAILURE': [],
        'CLASSIFICATION_UNKNOWN': [],
        'reports': []
    }
    
    start_time = time.time()
    
    for key, info in manifest.items():
        if models and key not in models and info['model'] not in models:
            continue
            
        results['total_attempted'] += 1
        artifact_path = info.get('artifact_path')
        make = info['manufacturer']
        model = info['model']
        
        rep = {
            'make': make,
            'model': model,
            'brochure_path': artifact_path,
            'pdf_valid': False,
            'page_count': 0,
            'text_extractable': False,
            'table_count': 0,
            'candidate_table_pages': [],
            'classifier': 'Unknown',
            'extraction_status': 'FAILED',
            'configs_extracted': 0,
            'configs_resolved': 0,
            'configs_unresolved': 0,
            'resolution_status': 'FAILED',
            'errors': []
        }
        
        if not artifact_path or not os.path.exists(artifact_path):
            rep['errors'].append('PDF missing')
            results['PDF_TEXT_FAILURE'].append(key)
            results['reports'].append(rep)
            continue
            
        rep['pdf_valid'] = True
        
        try:
            # 1. Structural Profiler
            sig = profile_pdf(artifact_path)
            rep['page_count'] = sig.total_pages
            rep['text_extractable'] = sig.text_pages > 0
            rep['candidate_table_pages'] = sig.table_pages
            rep['table_count'] = len(sig.table_pages)
            
            if sig.is_cid_corrupted:
                rep['errors'].append('PDF CID-font corruption detected.')
                results['PDF_TEXT_FAILURE'].append(key)
                results['reports'].append(rep)
                continue
                
            if not rep['text_extractable']:
                rep['errors'].append('PDF is image-only or lacks extractable text.')
                results['PDF_TEXT_FAILURE'].append(key)
                results['reports'].append(rep)
                continue
                
        except Exception as e:
            rep['errors'].append(f"Profiler error: {e}")
            results['PDF_TEXT_FAILURE'].append(key)
            results['reports'].append(rep)
            continue
            
        try:
            # 2. Classifier
            strategy = classify_layout(artifact_path, make, model)
            family_name = type(strategy).__name__
            rep['classifier'] = family_name
        except Exception as e:
            rep['errors'].append(f"Classification error: {e}")
            results['CLASSIFICATION_UNKNOWN'].append(key)
            results['reports'].append(rep)
            continue
            
        try:
            # 3. Extraction
            extractor = OEMBrochureExtractor(strategy)
            payloads = extractor.execute(artifact_path)
            rep['configs_extracted'] = len(payloads)
            
            if not payloads:
                rep['extraction_status'] = 'ZERO_CONFIGS'
                rep['errors'].append('0 configurations extracted')
                results['EXTRACTION_FAILURE'].append(key)
                results['reports'].append(rep)
                continue
                
            rep['extraction_status'] = 'SUCCESS'
            
        except Exception as e:
            rep['extraction_status'] = 'CRASH'
            rep['errors'].append(f"Extraction crash: {e}")
            results['EXTRACTION_FAILURE'].append(key)
            results['reports'].append(rep)
            continue
            
        try:
            # 4. Canonical Resolution
            gen_id = resolve_oem_generation(conn, make, model, None)
            make_slug = make.lower().replace(" ", "-")
            model_slug = model.lower().replace(" ", "-")
            res = process_oem_payload(conn, payloads, make_slug, model_slug, 1, gen_id)
            
            rep['configs_resolved'] = res['resolved']
            rep['configs_unresolved'] = res['unresolved']
            
            if res['resolved'] == 0:
                rep['resolution_status'] = 'UNRESOLVED'
                results['RESOLUTION_FAILURE'].append(key)
            elif res['resolved'] < len(payloads):
                rep['resolution_status'] = 'PARTIAL'
                results['GENERIC_PARTIAL'].append(key)
            else:
                rep['resolution_status'] = 'SUCCESS'
                results['GENERIC_SUCCESS'].append(key)
                
        except Exception as e:
            rep['resolution_status'] = 'CRASH'
            rep['errors'].append(f"Resolution crash: {e}")
            results['RESOLUTION_FAILURE'].append(key)
            
        results['reports'].append(rep)
        
    conn.close()
    
    report_path = "knowledge_base/sources/oem/batch_report.json"
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)
        
    print(f"\n--- BATCH EXTRACTION COMPLETE ({time.time() - start_time:.1f}s) ---")
    print(f"Attempted: {results['total_attempted']}")
    print(f"GENERIC_SUCCESS: {len(results['GENERIC_SUCCESS'])}")
    print(f"GENERIC_PARTIAL: {len(results['GENERIC_PARTIAL'])}")
    print(f"EXTRACTION_FAILURE: {len(results['EXTRACTION_FAILURE'])}")
    print(f"RESOLUTION_FAILURE: {len(results['RESOLUTION_FAILURE'])}")
    print(f"PDF_TEXT_FAILURE: {len(results['PDF_TEXT_FAILURE'])}")
    print(f"CLASSIFICATION_UNKNOWN: {len(results['CLASSIFICATION_UNKNOWN'])}")
    
    # Simple work queue printout
    print("\n--- RECOMMENDED WORK QUEUE ---")
    if results['EXTRACTION_FAILURE']:
        print("Priority 1: Fix Generic Extraction Logic (Affects:", len(results['EXTRACTION_FAILURE']), "models)")
    if results['CLASSIFICATION_UNKNOWN']:
        print("Priority 2: Implement New Layout Families (Affects:", len(results['CLASSIFICATION_UNKNOWN']), "models)")
    if results['RESOLUTION_FAILURE']:
        print("Priority 3: Update DB Resolver Synonyms (Affects:", len(results['RESOLUTION_FAILURE']), "models)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--models', nargs='+')
    args = parser.parse_args()
    
    if args.all:
        run_batch()
    elif args.models:
        run_batch(args.models)
    else:
        print("Specify --all or --models")
