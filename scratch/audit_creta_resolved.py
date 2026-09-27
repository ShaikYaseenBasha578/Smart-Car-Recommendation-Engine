import sqlite3
from knowledge_base.ingestion.common.resolver import resolve_variant
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

conn = sqlite3.connect("scratch/phase6_family_dryrun.sqlite")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

strategy = classify_layout("hyundai", "creta")
extractor = OEMBrochureExtractor(strategy)
payloads = extractor.execute("knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf")

cur.execute("SELECT id FROM generation WHERE model_id=(SELECT id FROM model WHERE name='Creta') ORDER BY id DESC LIMIT 1")
gen_id = cur.fetchone()[0]

print("RESOLVED CONFIGURATIONS:")
for p in payloads:
    v_name = p.get('variant_name')
    fuel = p.get('fuel_type')
    trans = p.get('transmission')
    
    v_id, status, cand = resolve_variant(conn, 'hyundai', 'creta', v_name, v_name, fuel, trans, None, None, generation_id=gen_id, source_name='oem')
    
    if status != 'unresolved':
        cur.execute("SELECT name FROM variant WHERE id=?", (v_id,))
        db_name = cur.fetchone()[0]
        print(f"[{v_name}] (Fuel: {fuel}, Trans: {trans}) -> Mapped to DB: [{db_name}] (Status: {status})")
