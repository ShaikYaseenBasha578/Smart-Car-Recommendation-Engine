import json
import os
from collections import defaultdict
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.field_map_oem import OEM_FIELD_RULES_CLEANED, clean_key, map_oem_fields, normalize_boolean

with open("knowledge_base/sources/oem/brochure_manifest.json", 'r') as f:
    manifest = json.load(f)

unresolved = 0
ambiguous = 0
fixed_by_dash = 0

for key, info in manifest.items():
    artifact_path = info.get('artifact_path')
    make = info['manufacturer']
    if not artifact_path or not os.path.exists(artifact_path): continue
    try:
        sig = profile_pdf(artifact_path)
        if sig.is_cid_corrupted or not (sig.text_pages > 0): continue
        strategy = classify_layout(artifact_path, make, info['model'])
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(artifact_path)
    except:
        continue
    if not payloads: continue
    
    for p in payloads:
        mapped_dict = map_oem_fields(p)
        for raw_k, raw_v in p.items():
            ck = clean_key(raw_k)
            if ck in OEM_FIELD_RULES_CLEANED:
                # check if unresolved
                tgt = OEM_FIELD_RULES_CLEANED[ck][0]
                res = False
                if isinstance(tgt, tuple):
                    res = any(mapped_dict.get(t) is not None for t in tgt)
                else:
                    res = mapped_dict.get(tgt) is not None
                    
                if not res:
                    val_str = str(raw_v).lower().strip()
                    # if we artificially use the OLD boolean logic where '-' is None
                    # we can see if it WOULD HAVE BEEN resolved if '-' was 1/0
                    # Wait, our current map_oem_fields HAS the '-' fix!
                    # So if it's STILL unresolved, it means it's truly ambiguous (like 'O', 'Optional', etc)
                    if val_str in ['o', 'optional', 'optionalδ', 'o (cvt only)', 'o (wireless)', 'o (wired)', '']:
                        ambiguous += 1
                    else:
                        unresolved += 1

print(f"Ambiguous (Correctly Unresolved): {ambiguous}")
print(f"Remaining Unresolved: {unresolved}")
