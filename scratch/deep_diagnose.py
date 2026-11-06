import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)), "..")))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import sys
import os
import json
import sqlite3
sys.path.append(os.getcwd())

from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import resolve_oem_generation

with open("knowledge_base/sources/oem/batch_report.json", 'r') as f:
    report = json.load(f)
    
failures = [r for r in report['reports'] if r.get('resolution_status') == 'UNRESOLVED']

conn = open_kb(KB_PATH)
conn.row_factory = sqlite3.Row

print("Deep Diagnostics:\n")
for r in failures:
    make = r['make']
    model = r['model']
    artifact_path = r['brochure_path']
    try:
        gen_id = resolve_oem_generation(conn, make, model, None)
        strategy = classify_layout(artifact_path, make, model)
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(artifact_path)
        
        valid_payloads = [p for p in payloads if len(p.get('variant_name', '')) > 1 and p.get('variant_name') not in ['Engine', 'Type', 'PETROL', 'DIESEL', 'Turbo']]
        
        if valid_payloads:
            print(f"--- {make} {model} ---")
            for p in valid_payloads[:5]:
                print(f"  OEM: {p.get('variant_name')} | {p.get('fuel_type')} | {p.get('transmission')} | {p.get('engine_name')}")
    except Exception:
        pass
