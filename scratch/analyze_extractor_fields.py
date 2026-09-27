import json
import os
import sys
from collections import defaultdict
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

with open("knowledge_base/sources/oem/brochure_manifest.json") as f:
    manifest = json.load(f)

extracted_fields = defaultdict(list)

for key, info in manifest.items():
    artifact_path = info.get('artifact_path')
    make = info['manufacturer']
    model = info['model']
    
    if not artifact_path or not os.path.exists(artifact_path): continue
    
    try:
        strategy = classify_layout(artifact_path, make, model)
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(artifact_path)
    except Exception:
        continue
        
    for p in payloads:
        for k, v in p.items():
            if k not in ['raw_variant_name', 'powertrain_type', 'transmission', 'fuel_type', 'engine_name', 'edition', 'variant_name']:
                extracted_fields[k.strip()].append((f"{make} {model}", v))

print(f"Found {len(extracted_fields)} unique field names.")
import json
with open("scratch/extracted_field_inventory.json", "w") as f:
    json.dump({k: v[:3] for k, v in extracted_fields.items()}, f, indent=2)
