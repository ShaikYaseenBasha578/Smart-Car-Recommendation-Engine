import json
import os
import traceback
from collections import defaultdict
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor
from knowledge_base.ingestion.oem.extractor.profiler import profile_pdf
from knowledge_base.ingestion.oem.field_map_oem import OEM_FIELD_RULES_CLEANED, clean_key, map_oem_fields

identity_fields = {'variant_name', 'fuel_type', 'transmission', 'engine_cc', 'engine_name', 'edition', 'powertrain_type', 'raw_variant_name'}

with open("knowledge_base/sources/oem/brochure_manifest.json", 'r') as f:
    manifest = json.load(f)

model_statuses = {}
field_stats = {
    'total_extracted': 0,
    'canonicalized': 0,
    'rule_exists_unresolved': 0,
    'canonicalizable_but_unmapped': 0,
    'unsupported_by_schema': 0,
    'marketing_text': 0,
    'ambiguous': 0,
    'extraction_artifact': 0,
    'identity_field': 0
}

canonicalizable_unmapped_details = defaultdict(lambda: {'count': 0, 'examples': set(), 'target': ''})

unsupported_keywords = ['isofix', 'defogger', 'headlamp', 'tail lamp', 'wiper', 'washer', 'door lock', 'keyless', 'immobilizer', 'alarm', 'antenna', 'spoiler', 'footwell', 'adjuster', 'door handle', 'tray', 'brakes', 'disc', 'drum', 'suspension', 'seat belt', 'mirror', 'window', 'charging port', 'usb', 'socket', 'glove box', 'lamp', 'roof rail', 'skid plate', 'grille', 'alloy', 'wheel', 'bumper', 'speaker', 'tweeter', 'amplifier', 'subwoofer', 'display', 'touchscreen', 'infotainment', 'navigation', 'bluetooth', 'radio', 'fm', 'am', 'aux', 'ipod', 'steering mounted', 'voice command', 'telematics', 'smartwatch', 'alexa', 'google', 'app', 'remote', 'key', 'push button', 'start stop', 'battery', 'motor', 'charging', 'charger', 'cable', 'warranty', 'service', 'maintenance', 'roadside', 'insurance', 'finance', 'loan', 'emi', 'down payment', 'offer', 'discount', 'exchange', 'bonus', 'corporate', 'loyalty', 'cashback', 'voucher', 'gift', 'accessory', 'merchandise', 'apparel', 'toy', 'scale model', 'sidescoop', 'telescopic', 'deactivation']
marketing_keywords = ['finish', 'trim', 'insert', 'accent', 'garnish', 'chrome', 'silver', 'black', 'piano', 'gloss', 'matte', 'metallic', 'pearl', 'dual tone', 'roof', 'decal', 'sticker', 'graphic', 'badge', 'emblem', 'logo', 'monogram', 'nameplate', 'lettering', 'typography', 'font', 'styling', 'design', 'aesthetic', 'look', 'appearance', 'presence', 'stance', 'profile', 'silhouette', 'proportion', 'dimension', 'color', 'colour', 'paint', 'upholstery', 'fabric', 'leather', 'pretensioner']
ambiguous_keywords = ['driver & passenger', 'side & curtain', 'front', 'rear', 'interior', 'exterior', 'safety', 'performance', 'comfort', 'convenience', 'dimensions', 'capacity']
canonical_keywords = ['abs', 'airbag', 'esc', 'hill', 'tpms', 'pressure', 'sensor', 'camera', 'adas', 'climate', 'ac vent', 'sunroof', 'ventilated', 'cruise', 'paddle', 'wireless', 'head up', 'heads up', 'drive mode', 'connect', 'android', 'apple', 'stability', 'traction']

for key, info in manifest.items():
    artifact_path = info.get('artifact_path')
    make = info['manufacturer']
    model = info['model']
    
    if not artifact_path or not os.path.exists(artifact_path):
        model_statuses[key] = 'PDF_TEXT_FAILURE'
        continue
        
    try:
        sig = profile_pdf(artifact_path)
        if sig.is_cid_corrupted or not (sig.text_pages > 0):
            model_statuses[key] = 'PDF_TEXT_FAILURE'
            continue
            
        strategy = classify_layout(artifact_path, make, model)
        extractor = OEMBrochureExtractor(strategy)
        payloads = extractor.execute(artifact_path)
        
        if not payloads:
            model_statuses[key] = 'EXTRACTION_FAILURE'
        else:
            model_statuses[key] = 'SUCCESS'
            
    except Exception as e:
        if "Unsupported" in str(e) or "Failed" in str(e) or "Cannot" in str(e) or "unsupported" in str(e) or "Could not structurally locate" in str(e):
            model_statuses[key] = 'CLASSIFICATION_UNKNOWN'
        else:
            print(f"UNEXPECTED ERROR on {key}: {e}")
            traceback.print_exc()
            model_statuses[key] = 'UNEXPECTED_ERROR'
        continue

    if model_statuses[key] != 'SUCCESS':
        continue
        
    for p in payloads:
        mapped_dict = map_oem_fields(p)
        for raw_k, raw_v in p.items():
            k_lower = raw_k.lower().strip()
            
            if k_lower in identity_fields:
                field_stats['identity_field'] += 1
                continue
                
            field_stats['total_extracted'] += 1
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
                        
                if resolved:
                    field_stats['canonicalized'] += 1
                else:
                    field_stats['rule_exists_unresolved'] += 1
            else:
                is_unsupported = any(kw in ck for kw in unsupported_keywords)
                is_marketing = any(kw in ck for kw in marketing_keywords)
                is_ambiguous = any(kw in k_lower for kw in ambiguous_keywords) and len(ck.split()) <= 3
                
                # Check for extraction artifacts: trailing "s s s", trailing numbers, asterisks, brackets at end, corrupted text
                is_artifact = (
                    len(ck) < 2 or 
                    '...' in raw_k or 
                    raw_k.startswith('*') or
                    '^' in raw_k or
                    ' s s' in raw_k.lower() or
                    'cfrooonlte' in raw_k.lower() or
                    'apai' in raw_k.lower() or 
                    raw_k.endswith('5') or 
                    '1in2bvu' in raw_k.lower() or
                    '[vector' in raw_v
                )
                
                if is_artifact:
                    field_stats['extraction_artifact'] += 1
                elif is_ambiguous:
                    field_stats['ambiguous'] += 1
                elif is_unsupported:
                    field_stats['unsupported_by_schema'] += 1
                elif is_marketing:
                    field_stats['marketing_text'] += 1
                else:
                    is_canon = any(kw in ck for kw in canonical_keywords)
                    if is_canon:
                        if 'sensor' in ck and 'parking' not in ck: is_canon = False
                        if 'camera' in ck and '360' not in ck and 'rear' not in ck and 'parking' not in ck and 'reverse' not in ck: is_canon = False
                        if 'airbag' in ck and '6' not in ck and 'dual' not in ck and 'driver' not in ck: is_canon = False
                        if 'side curtain' in ck or 'driver passenger' in ck: is_canon = False
                        
                    if is_canon:
                        field_stats['canonicalizable_but_unmapped'] += 1
                        canonicalizable_unmapped_details[raw_k]['count'] += 1
                        if len(canonicalizable_unmapped_details[raw_k]['examples']) < 3:
                            canonicalizable_unmapped_details[raw_k]['examples'].add(str(raw_v))
                        canonicalizable_unmapped_details[raw_k]['target'] = 'TBD'
                    else:
                        field_stats['unsupported_by_schema'] += 1

print("\n=== MODEL STATUSES ===")
status_counts = defaultdict(int)
for k, v in model_statuses.items():
    status_counts[v] += 1
for k, v in status_counts.items():
    print(f"{k}: {v}")
    
if 'UNEXPECTED_ERROR' in status_counts:
    print("WARNING: UNEXPECTED_ERROR ENCOUNTERED!")

print("\n=== FIELD MAPPING STATS ===")
for k, v in field_stats.items():
    print(f"{k}: {v}")

print("\n=== CANONICALIZABLE BUT UNMAPPED ===")
for k, v in canonicalizable_unmapped_details.items():
    print(f"'{k}' ({v['count']}) -> Examples: {list(v['examples'])}")

if field_stats['canonicalizable_but_unmapped'] == 0:
    print("SUCCESS: 0 Canonicalizable fields silently dropped!")
else:
    print("FAILED: Canonicalizable fields dropped!")
