import json

with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)

targets = ["Thar", "Alto K10", "Virtus", "Dzire", "Scorpio Classic", "Nexon", "Nexon EV", "Tiago", "Tiago EV"]
for r in report['reports']:
    if r['model'] in targets:
        print(f"\n[{r['model']}]")
        print(f"Classifier: {r.get('classifier')}")
        print(f"Configs Extracted: {r.get('configs_extracted')}")
        print(f"Configs Resolved: {r.get('configs_resolved')}")
        print(f"Status: {r.get('status', r.get('extraction_status'))}")
