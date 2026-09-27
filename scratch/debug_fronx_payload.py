import sys
import os
import sqlite3
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation
from knowledge_base.ingestion.common.resolver import resolve_variant

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"
strategy = classify_layout(pdf_path, "Maruti Suzuki", "Fronx")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute(pdf_path)

conn = sqlite3.connect("knowledge_base/carrec_kb.db")
gen_id = resolve_oem_generation(conn, "Maruti Suzuki", "Fronx", None)

for p in payloads:
    v_name = p.get('variant_name')
    fuel = p.get('fuel_type')
    trans = p.get('transmission')
    engine_name = p.get('engine_name')
    edition = p.get('edition')
    v_id, status, cand = resolve_variant(
        conn, "maruti-suzuki", "fronx", v_name, v_name, 
        fuel, trans, None, None, 
        generation_id=gen_id, active_only=False, source_name='oem',
        engine_name=engine_name, edition=edition
    )
    print(f"Payload: {v_name} | {fuel} | {trans} | {engine_name} -> Resolved: {v_id} ({status})")
    if not v_id and cand:
        print(f"  Candidates were: {[c['v_name'] for c in cand]}")

