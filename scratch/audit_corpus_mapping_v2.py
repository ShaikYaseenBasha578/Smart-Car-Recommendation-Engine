import json
import os
from collections import defaultdict

from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields

identity_fields = {'variant_name', 'fuel_type', 'transmission', 'engine_cc', 'engine_name', 'edition', 'powertrain_type', 'raw_variant_name'}

with open("knowledge_base/sources/oem/brochure_manifest.json", 'r') as f:
    manifest = json.load(f)

total_extracted = 0
total_mapped = 0
unmapped_counts = defaultdict(int)

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
        mapped_dict = map_oem_fields(p)
        for k, v in p.items():
            k_lower = k.lower().strip()
            if k_lower in identity_fields: continue
            total_extracted += 1
            # To check if it was mapped, we can't just check if k_lower is in dict because map_oem_fields returns canonical keys, not raw keys.
            # But map_oem_fields maps if clean_key(k) is in OEM_FIELD_RULES_CLEANED.
            # We can just see if mapping length > 0 if we mapped it individually, but it's simpler to import OEM_FIELD_RULES_CLEANED
            pass

from knowledge_base.ingestion.oem.field_map_oem import OEM_FIELD_RULES_CLEANED, clean_key
total_extracted = 0
total_mapped = 0
unmapped_counts = defaultdict(int)

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
            if clean_key(k) in OEM_FIELD_RULES_CLEANED:
                total_mapped += 1
            else:
                unmapped_counts[k] += 1

canonicalizable_remaining = 0
ambiguous = 0
unsupported = 0
marketing = 0
bugs = 0

print("--- REMAINING SUSPICIOUS UNMAPPED FIELDS ---")
# Keywords corresponding to canonical schema fields:
canon_keywords = ['abs', 'airbag', 'esc', 'hill', 'tpms', 'pressure', 'sensor', 'camera', 'adas', 'climate', 'ac vent', 'sunroof', 'ventilated', 'cruise', 'paddle', 'wireless', 'head up', 'heads up', 'drive mode', 'connect', 'android', 'apple']

for k, count in sorted(unmapped_counts.items(), key=lambda x: x[1], reverse=True):
    ck = clean_key(k)
    suspicious = False
    for kw in canon_keywords:
        if kw in ck:
            suspicious = True
            break
    if suspicious:
        # Filter out known non-canonical things that match keywords
        if 'sensor' in ck and 'parking' not in ck: suspicious = False
        if 'camera' in ck and '360' not in ck and 'rear' not in ck and 'parking' not in ck and 'reverse' not in ck: suspicious = False
        if 'airbag' in ck and '6' not in ck and 'dual' not in ck and 'driver' not in ck: suspicious = False
        if 'side curtain' in ck or 'driver passenger' in ck: suspicious = False # ambiguous
        
        # If still suspicious, print it out to check
        if suspicious:
            print(f"SUSPICIOUS: '{k}' ({count}) -> '{ck}'")
            
print(f"Total Extracted Non-Identity: {total_extracted}")
print(f"Total Mapped: {total_mapped}")
print(f"Total Unmapped: {total_extracted - total_mapped}")
