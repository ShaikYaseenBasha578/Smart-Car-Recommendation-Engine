import sys, json, traceback
sys.path.append('.')
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout
from knowledge_base.ingestion.oem.extractor.extractor import OEMBrochureExtractor

# Resolve actual paths from manifest
with open("knowledge_base/sources/oem/brochure_manifest.json") as f:
    manifest = json.load(f)

targets = [
    "Maruti Suzuki_Swift", "Maruti Suzuki_Dzire", "Volkswagen_Virtus",
    "Mahindra_Thar", "Hyundai_Creta", "Hyundai_Grand i10 Nios",
    "Maruti Suzuki_Fronx", "Maruti Suzuki_Baleno",
    "Tata_Nexon", "Tata_Nexon EV", "Tata_Tiago", "Tata_Tiago EV",
    "Maruti Suzuki_Alto K10"
]

print("--- TARGETED VALIDATION ---")
for t in targets:
    if t not in manifest:
        # Some are named differently, e.g. Tata_Nexon EV might be Tata_Nexon_EV
        # We will handle exact matching or skip with a warning
        print(f"\n--- {t} --- (NOT FOUND IN MANIFEST)")
        continue
        
    path = manifest[t]['artifact_path']
    make = manifest[t]['manufacturer']
    model = manifest[t]['model']
    
    print(f"\n--- {t} ---")
    try:
        strategy = classify_layout(path, make, model)
        strat_name = type(strategy).__name__
        print(f"Detected Strategy: {strat_name}")
        
        extractor = OEMBrochureExtractor(strategy)
        configs = extractor.execute(path)
        
        print(f"Configurations Extracted: {len(configs)}")
        if configs:
            print(f"Headers: {[c.get('raw_variant_name', '') for c in configs]}")
    except Exception as e:
        print(f"Extraction Failed: {type(e).__name__} - {e}")

