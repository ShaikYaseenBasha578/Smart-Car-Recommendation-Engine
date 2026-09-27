import sqlite3
import json
from knowledge_base.ingestion.common.resolver import SequenceMatcher, resolve_variant
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields

conn = sqlite3.connect("scratch/phase6_family_dryrun.sqlite")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

strategy = classify_layout("hyundai", "creta")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute("knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf")

cur.execute("SELECT id FROM generation WHERE model_id=(SELECT id FROM model WHERE name='Creta') ORDER BY id DESC LIMIT 1")
gen_id = cur.fetchone()[0]

cur.execute("""
    SELECT v.id, v.name, pt.fuel_type, v.transmission 
    FROM variant v 
    JOIN powertrain pt ON v.powertrain_id = pt.id 
    WHERE v.model_id=(SELECT id FROM model WHERE name='Creta') AND v.generation_id=?
""", (gen_id,))
db_variants = cur.fetchall()

print("UNRESOLVED CONFIGURATIONS:")
for p in payloads:
    mapped = map_oem_fields(p)
    raw_name = mapped.get('variant_name', p['raw_variant_name']); print(f'Mapped: {raw_name}'); print(mapped.get('variant_name'))
    fuel = mapped.get('fuel_type', p['powertrain_type'])
    trans = p['transmission']
    
    candidates = [v for v in db_variants if v['fuel_type'].lower() == fuel.lower()]
    
    v_id, status, cand = resolve_variant(conn, 'hyundai', 'creta', raw_name, raw_name, fuel, trans, None, None, generation_id=gen_id, source_name='oem')
    
    if status == 'unresolved':
        scores = []
        for v in candidates:
            score = SequenceMatcher(None, raw_name.lower(), v['name'].lower()).ratio() * 100
            scores.append((v['name'], round(score, 2), v['transmission']))
        scores.sort(key=lambda x: x[1], reverse=True)
        print(f"[{raw_name}] (Fuel: {fuel}, Trans: {trans})")
        print(f"  Top DB Candidates: {scores[:3]}")
