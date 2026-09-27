import json, os, sys
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

targets = ["Thar", "Alto K10", "Virtus", "Dzire", "Nexon"]
with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)
    
for r in report['reports']:
    if r['model'] in targets:
        print(f"\n==== {r['model']} ====")
        strategy = classify_layout(r['brochure_path'], r['make'], r['model'])
        configs = strategy.extract(r['brochure_path'])
        names = [c.raw_variant_name for c in configs]
        print(f"Extracted Trims: {names}")
        if configs:
            print(f"Sample Features for {names[0]}:")
            for f in configs[0].fields[:5]:
                print(f"  {f.field_name}: {f.raw_value}")
