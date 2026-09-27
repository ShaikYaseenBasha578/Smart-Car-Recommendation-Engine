import json

with open("knowledge_base/sources/oem/batch_report.json") as f:
    r = json.load(f)

print("SUCCESS:", r.get("GENERIC_SUCCESS", []))
print("PARTIAL:", r.get("GENERIC_PARTIAL", []))
