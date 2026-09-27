import json
import os
from collections import defaultdict

from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.field_map_oem import OEM_FIELD_RULES

identity_fields = {'variant_name', 'fuel_type', 'transmission', 'engine_cc', 'engine_name', 'edition', 'powertrain_type', 'raw_variant_name'}

with open("knowledge_base/sources/oem/brochure_manifest.json", 'r') as f:
    manifest = json.load(f)

total_extracted = 0
total_mapped = 0
unmapped_counts = defaultdict(int)
unmapped_examples = defaultdict(list)

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
        
    if not payloads: continue
    
    for p in payloads:
        for k, v in p.items():
            k_lower = k.lower().strip()
            if k_lower in identity_fields: continue
            
            total_extracted += 1
            if k_lower in OEM_FIELD_RULES:
                total_mapped += 1
            else:
                unmapped_counts[k_lower] += 1
                if len(unmapped_examples[k_lower]) < 3 and v not in unmapped_examples[k_lower]:
                    unmapped_examples[k_lower].append(v)

print(f"Total Extracted Non-Identity: {total_extracted}")
print(f"Total Mapped: {total_mapped}")
print(f"Total Unmapped Instances: {total_extracted - total_mapped}")
print(f"Unique Unmapped Field Names: {len(unmapped_counts)}\n")

sorted_unmapped = sorted(unmapped_counts.items(), key=lambda x: x[1], reverse=True)
for k, count in sorted_unmapped[:50]:
    print(f"Field: '{k}' | Count: {count} | Examples: {unmapped_examples[k]}")

