import sys
import os
import json
import sqlite3
sys.path.append(os.getcwd())

from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import resolve_oem_generation
from knowledge_base.ingestion.common.resolver import resolve_variant

with open("knowledge_base/sources/oem/batch_report.json", 'r') as f:
    report = json.load(f)
    
failures = [r for r in report['reports'] if r.get('resolution_status') == 'UNRESOLVED']

conn = sqlite3.connect("knowledge_base/carrec_kb.db")
conn.row_factory = sqlite3.Row

print("Diagnostics for 23 RESOLUTION_FAILURE models:\n")
for r in failures:
    make = r['make']
    model = r['model']
    artifact_path = r['brochure_path']
    print(f"--- {make} {model} ---")
    
    try:
        gen_id = resolve_oem_generation(conn, make, model, None)
        strategy = classify_layout(artifact_path, make, model)
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(artifact_path)
        
        make_slug = make.lower().replace(" ", "-")
        model_slug = model.lower().replace(" ", "-")
        
        fail_count = 0
        for p in payloads:
            v_name = p.get('variant_name')
            fuel = p.get('fuel_type')
            trans = p.get('transmission')
            engine_name = p.get('engine_name')
            edition = p.get('edition')
            
            v_id, status, cand = resolve_variant(
                conn, make_slug, model_slug, v_name, v_name, 
                fuel, trans, None, None, 
                generation_id=gen_id, active_only=False, source_name='oem',
                engine_name=engine_name, edition=edition
            )
            
            if not v_id:
                print(f"OEM: {v_name} | {fuel} | {trans} | {engine_name}")
                if cand:
                    print(f"  Top Candidates:")
                    for c in cand[:2]:
                        print(f"    - DB: {c['v_name']} ({c['fuel_type']} {c['transmission']}) [Score: {c['score']}]")
                else:
                    print("  Top Candidates: None (Filtered out)")
                fail_count += 1
                if fail_count >= 2:
                    break
                    
    except Exception as e:
        print(f"  Error: {e}")
