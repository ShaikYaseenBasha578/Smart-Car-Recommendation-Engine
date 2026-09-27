import json
import os
from collections import defaultdict
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.field_map_oem import OEM_FIELD_RULES_CLEANED, clean_key, map_oem_fields, normalize_boolean

identity_fields = {'variant_name', 'fuel_type', 'transmission', 'engine_cc', 'engine_name', 'edition', 'powertrain_type', 'raw_variant_name'}

with open("knowledge_base/sources/oem/brochure_manifest.json", 'r') as f:
    manifest = json.load(f)

unresolved_cases = defaultdict(lambda: defaultdict(int))
total_unresolved = 0

count = 0
for key, info in manifest.items():
    artifact_path = info.get('artifact_path')
    make = info['manufacturer']
    model = info['model']
    
    if not artifact_path or not os.path.exists(artifact_path): continue
    try:
        sig = profile_pdf(artifact_path)
        if sig.is_cid_corrupted or not (sig.text_pages > 0): continue
        strategy = classify_layout(artifact_path, make, model)
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(artifact_path)
    except Exception:
        continue
        
    if not payloads: continue
    
    for p in payloads:
        mapped_dict = map_oem_fields(p)
        for raw_k, raw_v in p.items():
            if raw_k.lower().strip() in identity_fields: continue
            
            ck = clean_key(raw_k)
            if ck in OEM_FIELD_RULES_CLEANED:
                target_field = OEM_FIELD_RULES_CLEANED[ck][0]
                resolved = False
                if isinstance(target_field, tuple):
                    for tgt in target_field:
                        if tgt in mapped_dict and mapped_dict[tgt] is not None:
                            resolved = True
                else:
                    if target_field in mapped_dict and mapped_dict[target_field] is not None:
                        resolved = True
                        
                if not resolved:
                    total_unresolved += 1
                    unresolved_cases[ck][str(raw_v)] += 1
                    print(f"UNRESOLVED: {ck} | VAL: {raw_v}")

print(f"Total Unresolved: {total_unresolved}")
