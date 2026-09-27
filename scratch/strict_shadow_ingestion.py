import os
import json
import sqlite3
import shutil
import traceback
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

def run_pass(db_path, pass_num):
    with open("knowledge_base/sources/oem/brochure_manifest.json", 'r') as f:
        manifest = json.load(f)
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None
    
    statuses = {}
    
    for key, info in manifest.items():
        artifact_path = info.get('artifact_path')
        make = info['manufacturer']
        model = info['model']
        
        if not artifact_path or not os.path.exists(artifact_path):
            statuses[key] = 'PDF_TEXT_FAILURE'
            continue
            
        try:
            sig = profile_pdf(artifact_path)
            if sig.is_cid_corrupted or not (sig.text_pages > 0):
                statuses[key] = 'PDF_TEXT_FAILURE'
                continue
                
            strategy = classify_layout(artifact_path, make, model)
            extractor = OEMBrochureExtractor(strategy)
            payloads = extractor.execute(artifact_path)
        except Exception as e:
            if "Unsupported" in str(e) or "Failed" in str(e) or "Cannot" in str(e):
                statuses[key] = 'CLASSIFICATION_UNKNOWN'
            else:
                print(f"UNEXPECTED ERROR on {key} (Extraction): {e}")
                traceback.print_exc()
                statuses[key] = 'UNEXPECTED_ERROR'
            continue
            
        if not payloads:
            statuses[key] = 'EXTRACTION_FAILURE'
            continue
        
        try:
            conn.execute('BEGIN TRANSACTION')
            gen_id = resolve_oem_generation(conn, make, model, None)
            make_slug = make.lower().replace(" ", "-")
            model_slug = model.lower().replace(" ", "-")
            process_oem_payload(conn, payloads, make_slug, model_slug, 1, gen_id)
            conn.execute('COMMIT')
            statuses[key] = 'SUCCESS'
        except Exception as e:
            conn.execute('ROLLBACK')
            if "Generation Pinning Failed" in str(e):
                statuses[key] = 'GENERATION_PIN_FAILURE'
            else:
                print(f"FATAL AUDIT ERROR on {key} (Ingestion):")
                traceback.print_exc()
                statuses[key] = 'UNEXPECTED_ERROR'
                raise e
    
    conn.close()
    
    # Print status counts for pass
    status_counts = defaultdict(int)
    for s in statuses.values():
        status_counts[s] += 1
    print(f"\n--- PASS {pass_num} MODEL STATUSES ---")
    for k, v in status_counts.items():
        print(f"{k}: {v}")
    
    if 'UNEXPECTED_ERROR' in status_counts:
        print("WARNING: UNEXPECTED ERROR IN THIS PASS!")

def main():
    isolated_db = "scratch/isolated_auth_kb.db"
    shutil.copy2("knowledge_base/carrec_kb.db", isolated_db)
    
    tables = ['manufacturer', 'model', 'generation', 'variant', 'powertrain', 'source_observation', 'field_provenance']
    
    snap0 = {t: get_table_snapshot(isolated_db, t) for t in tables}
    
    print("Running Pass 1...")
    run_pass(isolated_db, 1)
    
    snap1 = {t: get_table_snapshot(isolated_db, t) for t in tables}
    
    print("\n--- PASS 1 DIFFS ---")
    for t in tables:
        d = diff_snapshots(snap0[t], snap1[t])
        print(f"Table {t}: {len(d['added'])} added, {len(d['deleted'])} deleted, {len(d['modified'])} modified")
        if t == 'variant' and d['modified']:
            for m in d['modified']:
                print(f"  Variant {m['id']} mutations: {m['changes']}")
        if t == 'powertrain' and d['modified']:
            for m in d['modified']:
                print(f"  Powertrain {m['id']} mutations: {m['changes']}")
                
    new_prov = diff_snapshots(snap0['field_provenance'], snap1['field_provenance'])['added']
    print("\n--- PROVENANCE RECONCILIATION ---")
    accepted = rejected = confirmed = other = 0
    print("ID | Variant ID | Field Name | Accepted Value | Decision | Source Obs ID")
    for p in new_prov:
        if p['decision'] == 'accepted': accepted += 1
        elif p['decision'] == 'rejected': rejected += 1
        elif p['decision'] == 'confirmed': confirmed += 1
        else: other += 1
        # print(f"{p['id']} | {p['variant_id']} | {p['field_name']} | {p['accepted_value']} | {p['decision']} | {p['source_observation_id']}")
    print(f"Total: {len(new_prov)} | Accepted: {accepted} | Rejected: {rejected} | Confirmed: {confirmed} | Other: {other}")
    
    print("\nRunning Pass 2 (Idempotency)...")
    run_pass(isolated_db, 2)
    
    snap2 = {t: get_table_snapshot(isolated_db, t) for t in tables}
    
    print("\n--- PASS 2 DIFFS (EXPECT ZERO) ---")
    idempotency_clean = True
    for t in tables:
        d = diff_snapshots(snap1[t], snap2[t])
        print(f"Table {t}: {len(d['added'])} added, {len(d['deleted'])} deleted, {len(d['modified'])} modified")
        if d['added'] or d['deleted'] or d['modified']:
            idempotency_clean = False
    
    if idempotency_clean:
        print("IDEMPOTENCY: TRUE")
    else:
        print("IDEMPOTENCY: FALSE")

if __name__ == '__main__':
    main()
