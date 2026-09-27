import json, sqlite3, os, sys
from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.ingest_oem import process_oem_payload, resolve_oem_generation

print("STARTING IDEMPOTENCY PASS...")
manifest_path = "knowledge_base/sources/oem/brochure_manifest.json"
with open(manifest_path, 'r') as f: manifest = json.load(f)
conn = sqlite3.connect("scratch/idempotency_kb.db")
conn.row_factory = sqlite3.Row
conn.isolation_level = None
conn.execute('BEGIN TRANSACTION')

total_updated = 0
for key, info in manifest.items():
    artifact_path = info.get('artifact_path')
    make, model = info['manufacturer'], info['model']
    if not artifact_path or not os.path.exists(artifact_path): continue
    sig = profile_pdf(artifact_path)
    if sig.is_cid_corrupted or not (sig.text_pages > 0): continue
    try:
        strategy = classify_layout(artifact_path, make, model)
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(artifact_path)
    except Exception: continue
    if not payloads: continue
    try:
        gen_id = resolve_oem_generation(conn, make, model, None)
        res = process_oem_payload(conn, payloads, make.lower().replace(" ", "-"), model.lower().replace(" ", "-"), 1, gen_id)
        total_updated += res['updated']
    except Exception: pass

conn.execute('COMMIT')
conn.close()
print(f"IDEMPOTENCY PASS COMPLETE. Total new fields updated: {total_updated}")
if total_updated > 0: sys.exit(1)
