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
    
partials = [r for r in report['reports'] if r.get('resolution_status') == 'PARTIAL']

conn = sqlite3.connect("knowledge_base/carrec_kb.db")
conn.row_factory = sqlite3.Row

print("Diagnostics for PARTIAL models:\n")
for r in partials:
    make = r['make']
    model = r['model']
    artifact_path = r['brochure_path']
    try:
        gen_id = resolve_oem_generation(conn, make, model, None)
        strategy = classify_layout(artifact_path, make, model)
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(artifact_path)
        
        make_slug = make.lower().replace(" ", "-")
        model_slug = model.lower().replace(" ", "-")
        
        unresolved = []
        for p in payloads:
            v_name = p.get('variant_name')
            fuel = p.get('fuel_type')
            trans = p.get('transmission')
            engine = p.get('engine_name')
            
            v_id, status, cand = resolve_variant(
                conn, make_slug, model_slug, v_name, v_name, 
                fuel, trans, None, None, 
                generation_id=gen_id, active_only=False, source_name='oem',
                engine_name=engine, edition=p.get('edition')
            )
            if not v_id:
                unresolved.append((v_name, fuel, trans, engine, cand))
                
        if unresolved:
            print(f"--- {make} {model} (Failed {len(unresolved)} of {len(payloads)}) ---")
            for u in unresolved[:3]:
                print(f"  OEM: {u[0]} | {u[1]} | {u[2]} | {u[3]}")
                if u[4]:
                    print(f"    Candidates: {[c['v_name'] for c in u[4][:2]]}")
    except Exception as e:
        pass
