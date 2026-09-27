import os
import json
import sqlite3
import shutil
from collections import defaultdict

from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation

def get_table_snapshot(db_path, table):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT * FROM {table}")
    rows = {row['id']: dict(row) for row in c.fetchall()}
    conn.close()
    return rows

def diff_snapshots(snap_before, snap_after):
    diffs = {'added': [], 'deleted': [], 'modified': []}
    for k in snap_after:
        if k not in snap_before:
            diffs['added'].append(snap_after[k])
        elif snap_before[k] != snap_after[k]:
            mods = {}
            for col in snap_after[k]:
                if snap_after[k][col] != snap_before[k][col]:
                    mods[col] = {'old': snap_before[k][col], 'new': snap_after[k][col]}
            if mods:
                diffs['modified'].append({'id': k, 'changes': mods})
    for k in snap_before:
        if k not in snap_after:
            diffs['deleted'].append(snap_before[k])
    return diffs

def run_ingestion(db_path, pass_name):
    print(f"\n--- RUNNING {pass_name} on {db_path} ---")
    with open("knowledge_base/sources/oem/brochure_manifest.json", 'r') as f:
        manifest = json.load(f)
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None
    
    statuses = defaultdict(int)
    
    for key, info in manifest.items():
        artifact_path = info.get('artifact_path')
        make = info['manufacturer']
        model = info['model']
        
        if not artifact_path or not os.path.exists(artifact_path):
            statuses["PDF_TEXT_FAILURE"] += 1
            continue
            
        try:
            sig = profile_pdf(artifact_path)
            if sig.is_cid_corrupted or not (sig.text_pages > 0):
                statuses["PDF_TEXT_FAILURE"] += 1
                continue
                
            strategy = classify_layout(artifact_path, make, model)
            extractor = OEMBrochureExtractor(strategy)
            payloads = extractor.execute(artifact_path)
        except Exception as e:
            err_str = str(e)
            if "borderless" in err_str.lower():
                statuses["EXTRACTION_FAILURE"] += 1
            elif "quarantine" in err_str.lower():
                statuses["CLASSIFICATION_UNKNOWN"] += 1
            else:
                statuses["UNEXPECTED_ERROR"] += 1
            continue
            
        if not payloads:
            statuses["EXTRACTION_FAILURE"] += 1
            continue
            
        success_count = 0
        try:
            conn.execute('BEGIN TRANSACTION')
            gen_result = resolve_oem_generation(conn, make, model, info.get('year'))
            if not gen_result:
                conn.execute('ROLLBACK')
                statuses["RESOLUTION_FAILURE"] += 1
                continue
                
            generation_id = gen_result
            for p in payloads:
                p['manufacturer'] = make
                p['model'] = model
                p['generation_id'] = generation_id
                process_oem_payload(conn, p)
                success_count += 1
                
            conn.execute('COMMIT')
            statuses["SUCCESS"] += 1
        except Exception as e:
            try:
                conn.execute('ROLLBACK')
            except:
                pass
            print(f"TRANSACTION ERROR on {make} {model}: {e}")
            statuses["UNEXPECTED_ERROR"] += 1
            
    conn.close()
    return dict(statuses)

def snapshot_all(db_path):
    return {t: get_table_snapshot(db_path, t) for t in ['manufacturer', 'model', 'generation', 'variant', 'powertrain', 'source_observation', 'field_provenance']}

if __name__ == "__main__":
    prod_db = "knowledge_base/carrec_kb.db"
    
    snap_before = snapshot_all(prod_db)
    statuses_1 = run_ingestion(prod_db, "PRODUCTION INGESTION")
    snap_after = snapshot_all(prod_db)
    
    diffs_1 = {}
    tables = ['manufacturer', 'model', 'generation', 'variant', 'powertrain', 'source_observation', 'field_provenance']
    
    print("\n--- DIFFS FOR PRODUCTION INGESTION ---")
    for table in tables:
        d = diff_snapshots(snap_before[table], snap_after[table])
        diffs_1[table] = d
        print(f"Table {table}: {len(d['added'])} added, {len(d['deleted'])} deleted, {len(d['modified'])} modified")
        
        if len(d['modified']) > 0:
            for mod in d['modified']:
                print(f"  {table.capitalize()} {mod['id']} mutations: {mod['changes']}")
    
    # Check mutations
    expected_mutation_valid = False
    var_mods = diffs_1['variant']['modified']
    if len(var_mods) == 1 and var_mods[0]['id'] == 669 and 'paddle_shifters' in var_mods[0]['changes']:
        old_val = var_mods[0]['changes']['paddle_shifters']['old']
        new_val = var_mods[0]['changes']['paddle_shifters']['new']
        if old_val is None and new_val == 0:
            expected_mutation_valid = True
            
    if not expected_mutation_valid or len(var_mods) != 1:
        print("FATAL: Canonical mutation check failed!")
        
    for tbl in ['manufacturer', 'model', 'generation', 'powertrain']:
        if diffs_1[tbl]['modified'] or diffs_1[tbl]['added'] or diffs_1[tbl]['deleted']:
            print(f"FATAL: Unexpected mutations in {tbl}")

    # Post-production idempotency
    idem_db = "scratch/carrec_kb_phase6_postproduction_idempotency.db"
    shutil.copyfile(prod_db, idem_db)
    
    snap_idem_before = snapshot_all(idem_db)
    statuses_2 = run_ingestion(idem_db, "POST-PRODUCTION IDEMPOTENCY")
    snap_idem_after = snapshot_all(idem_db)
    
    diffs_2 = {}
    is_idempotent = True
    print("\n--- DIFFS FOR IDEMPOTENCY ---")
    for table in tables:
        d = diff_snapshots(snap_idem_before[table], snap_idem_after[table])
        diffs_2[table] = d
        print(f"Table {table}: {len(d['added'])} added, {len(d['deleted'])} deleted, {len(d['modified'])} modified")
        if d['added'] or d['deleted'] or d['modified']:
            is_idempotent = False
            
    print(f"\nIDEMPOTENCY: {is_idempotent}")
    
    added_prov = diffs_1['field_provenance']['added']
    accepted = sum(1 for p in added_prov if p['decision'] == 'ACCEPTED')
    rejected = sum(1 for p in added_prov if p['decision'] == 'REJECTED')
    confirmed = sum(1 for p in added_prov if p['decision'] == 'CONFIRMED')
    total = len(added_prov)
    
    with open('scratch/production_ingestion_results.json', 'w') as f:
        json.dump({
            'statuses': statuses_1,
            'prov': {'total': total, 'accepted': accepted, 'rejected': rejected, 'confirmed': confirmed},
            'source_obs_added': len(diffs_1['source_observation']['added']),
            'is_idempotent': is_idempotent,
            'canonical_mutation_valid': expected_mutation_valid,
            'variant_mutations_count': len(var_mods)
        }, f, indent=2)
