import json, os, sys
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.families.borderless_variant_column_matrix import BorderlessVariantColumnMatrixStrategy

targets = ["Scorpio Classic", "Dzire", "Thar", "Virtus", "Nexon", "Nexon EV", "Tiago", "Tiago EV", "Alto K10"]

with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)

for r in report['reports']:
    model = r['model']
    if model not in targets: continue
    
    print(f"\n{'='*50}\nMODEL: {model}\nBROCHURE: {r['brochure_path']}")
    print(f"CLASSIFIER: BorderlessVariantColumnMatrixStrategy")
    
    try:
        strategy = BorderlessVariantColumnMatrixStrategy()
        configs = strategy.extract(r['brochure_path'])
        print(f"STRUCTURAL STATUS: SUCCESS")
        print(f"EXTRACTED CONFIG COUNT: {len(configs)}")
        
        names = [c.raw_variant_name for c in configs]
        print(f"EXTRACTED RAW VARIANT NAMES: {names}")
        
        pts = [c.powertrain_type for c in configs]
        trans = [c.transmission for c in configs]
        print(f"POWERTRAIN EVIDENCE: {pts}")
        print(f"TRANSMISSION EVIDENCE: {trans}")
        
        print(f"FIELDS PER CONFIGURATION: {[len(c.fields) for c in configs]}")
        if configs and configs[0].fields:
            print("SAMPLE EXTRACTED FIELDS (from config 0):")
            for f in configs[0].fields[:5]:
                print(f"  [{f.source_page}] {f.field_name} -> {f.raw_value}")
                
    except Exception as e:
        print(f"STRUCTURAL STATUS: FAILED CLOSED")
        print(f"FAIL-CLOSED REASON IF FAILED: {str(e)}")

