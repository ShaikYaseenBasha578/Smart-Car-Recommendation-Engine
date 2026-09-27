import sys, json, os, time
import pdfplumber
import sqlite3
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import resolve_oem_generation, process_oem_payload
from knowledge_base.ingestion.common.resolver import resolve_variant

def setup_scratch_db():
    os.system("cp knowledge_base/carrec_kb.db scratch/integration_test_kb.db")
    conn = sqlite3.connect("scratch/integration_test_kb.db")
    conn.row_factory = sqlite3.Row
    return conn

def verify_extraction(targets):
    print("\n=== TARGETED REAL-CORPUS TESTS ===")
    with open("knowledge_base/sources/oem/brochure_manifest.json") as f:
        manifest = json.load(f)

    for t in targets:
        if t not in manifest:
            print(f"[{t}] SKIPPED - Not in manifest")
            continue
            
        path = manifest[t]['artifact_path']
        make = manifest[t]['manufacturer']
        model = manifest[t]['model']
        
        try:
            strategy = classify_layout(path, make, model)
            strat_name = type(strategy).__name__
            
            extractor = OEMBrochureExtractor(strategy)
            configs = extractor.execute(path)
            
            status = "SUCCESS" if configs else "EMPTY"
            print(f"[{t}] {strat_name} | Status: {status} | Configs: {len(configs)}")
        except Exception as e:
            print(f"[{t}] {type(strategy).__name__ if 'strategy' in locals() else 'Classifier'} | Status: EXTRACTION_FAILURE | Reason: {e}")

def verify_identity_safety(conn):
    print("\n=== IDENTITY SAFETY & FAIL-CLOSED ===")
    
    # 1. Technical-table garbage
    # Pass garbage strings and verify they return None (fail closed)
    v_id, status, cand = resolve_variant(conn, "maruti suzuki", "swift", "3995 mm", "3995 mm", None, None, None, None, source_name='oem', active_only=False, generation_id=3) # Assuming Swift model_id or generation_id exists, we can use generation_id=4 or None
    print(f"[Garbage Test - '3995 mm'] Resolves: {v_id is not None} | Status: {status}")

    # 2. Wrong fuel
    # E.g. Maruti Swift but passing Diesel
    v_id, status, cand = resolve_variant(conn, "maruti suzuki", "swift", "LXi", "LXi", "Diesel", None, None, None, source_name='oem', active_only=False, generation_id=4)
    print(f"[Cross-Fuel Test - 'LXi Diesel'] Resolves: {v_id is not None} | Status: {status}")

    # 3. Wrong transmission
    v_id, status, cand = resolve_variant(conn, "maruti suzuki", "swift", "LXi", "LXi", "Petrol", "AMT", None, None, source_name='oem', active_only=False, generation_id=4)
    print(f"[Cross-Transmission Test - 'LXi AMT'] Resolves: {v_id is not None} | Status: {status}")

def verify_generation_pinning(conn):
    print("\n=== GENERATION PINNING ===")
    try:
        resolve_oem_generation(conn, "Maruti Suzuki", "Swift", 2050)
    except ValueError as e:
        print(f"[Zero Match Test] Passed: {e}")
        
    try:
        resolve_oem_generation(conn, "Maruti Suzuki", "Swift", None)
    except ValueError as e:
        print(f"[Multiple Match Test] Passed: {e}")
        
    try:
        gid = resolve_oem_generation(conn, "Maruti Suzuki", "Swift", 2024)
        print(f"[Exact Match Test] Passed: ID={gid}")
    except Exception as e:
        print(f"[Exact Match Test] Failed: {e}")

def verify_determinism():
    print("\n=== DETERMINISM ===")
    with open("knowledge_base/sources/oem/brochure_manifest.json") as f:
        manifest = json.load(f)
    path = manifest["Maruti Suzuki_Swift"]["artifact_path"]
    make = manifest["Maruti Suzuki_Swift"]["manufacturer"]
    model = manifest["Maruti Suzuki_Swift"]["model"]
    
    strategy = classify_layout(path, make, model)
    extractor = OEMBrochureExtractor(strategy)
    configs1 = extractor.execute(path)
    
    strategy2 = classify_layout(path, make, model)
    extractor2 = OEMBrochureExtractor(strategy2)
    configs2 = extractor2.execute(path)
    
    match = (str(configs1) == str(configs2))
    print(f"Multiple Passes Identical: {match}")

if __name__ == "__main__":
    conn = setup_scratch_db()
    targets_a = ["Maruti Suzuki_Swift", "Hyundai_Creta", "Hyundai_Grand i10 Nios", "Maruti Suzuki_Fronx", "Maruti Suzuki_Baleno", "Maruti Suzuki_Brezza", "Maruti Suzuki_XL6"]
    targets_b = ["Maruti Suzuki_Dzire", "Volkswagen_Virtus", "Mahindra_Thar"]
    targets_c = ["Tata_Nexon", "Tata_Nexon EV", "Tata_Tiago", "Tata_Tiago EV", "Maruti Suzuki_Alto K10"]
    
    verify_extraction(targets_a + targets_b + targets_c)
    verify_identity_safety(conn)
    verify_generation_pinning(conn)
    verify_determinism()
    conn.close()
