import sys, os, json
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.classifier import classify_layout

with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)

# Find models that extracted configs but couldn't resolve them
res_failures = [r for r in report['reports'] if r['configs_extracted'] > 0 and r['configs_resolved'] == 0]

print(f"Found {len(res_failures)} models with complete resolution failure.")

for r in res_failures:
    model = r['model']
    path = r['brochure_path']
    try:
        strategy = classify_layout(path, "", model)
        if strategy:
            configs = strategy.extract(path)
            names = list(set([str(c.raw_variant_name) for c in configs]))
            print(f"[{model}] {strategy.__class__.__name__} -> Extracted {len(configs)} configs. Unique names: {names[:10]}")
        else:
            print(f"[{model}] No strategy classified.")
    except Exception as e:
        print(f"[{model}] ERROR: {e}")
        
# Find partial resolution failures
partial = [r for r in report['reports'] if r['configs_extracted'] > 0 and r['configs_resolved'] > 0 and r['configs_unresolved'] > 0]
print(f"\nFound {len(partial)} models with partial resolution failure.")
for r in partial:
    print(f"[{r['model']}] {r['classifier']} -> Extracted: {r['configs_extracted']}, Resolved: {r['configs_resolved']}, Unresolved: {r['configs_unresolved']}")
