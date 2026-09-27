import json

with open("knowledge_base/sources/oem/batch_report.json") as f:
    r = json.load(f)

for k, v in r.items():
    if isinstance(v, list) and "Mahindra_Thar" in v:
        print(f"Mahindra_Thar was in: {k}")
        
    if isinstance(v, list) and "Maruti Suzuki_Swift" in v:
        print(f"Maruti Suzuki_Swift was in: {k}")
