import json
import os
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields

with open("knowledge_base/sources/oem/brochure_manifest.json", "r") as f:
    manifest = json.load(f)

table = []
table.append("Model | Extracted Configs | Total Fields Extracted | Total Fields Mapped | Status")
table.append("---|---|---|---|---")

for key, info in manifest.items():
    artifact = info.get('artifact_path')
    make = info['manufacturer']
    model = info['model']
    
    if not artifact or not os.path.exists(artifact):
        table.append(f"{make} {model} | 0 | 0 | 0 | PDF_MISSING")
        continue
        
    try:
        strategy = classify_layout(artifact, make, model)
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(artifact)
    except Exception as e:
        table.append(f"{make} {model} | 0 | 0 | 0 | FAILED ({type(e).__name__})")
        continue
        
    if not payloads:
        table.append(f"{make} {model} | 0 | 0 | 0 | ZERO_CONFIGS")
        continue
        
    extracted_fields_cnt = 0
    mapped_fields_cnt = 0
    
    for p in payloads:
        extracted_fields_cnt += len(p)
        mapped = map_oem_fields(p)
        mapped_fields_cnt += len(mapped)
        
    table.append(f"{make} {model} | {len(payloads)} | {extracted_fields_cnt} | {mapped_fields_cnt} | SUCCESS")

with open("scratch/per_model_field_table.md", "w") as f:
    f.write("\n".join(table))
print("Per-model table generated.")
