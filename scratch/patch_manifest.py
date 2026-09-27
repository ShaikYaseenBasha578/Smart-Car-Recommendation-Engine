import json

with open("knowledge_base/sources/oem/brochure_manifest.json", "r") as f:
    data = json.load(f)

for key, val in data.items():
    if val["status"] == "OFFICIAL_BROCHURE_NOT_FOUND":
        val["status"] = "OTHER_FAILURE"
        val["verification_status"] = "SEARCH_ENGINE_WAF_BLOCK_HTTP_202"

with open("knowledge_base/sources/oem/brochure_manifest.json", "w") as f:
    json.dump(data, f, indent=2)
