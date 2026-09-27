import json
with open("knowledge_base/sources/oem/batch_report.json", "r") as f:
    report = json.load(f)

print(f"GENERIC_SUCCESS = {len(report.get('GENERIC_SUCCESS', []))}")
print(f"GENERIC_PARTIAL = {len(report.get('GENERIC_PARTIAL', []))}")
print(f"EXTRACTION_FAILURE = {len(report.get('EXTRACTION_FAILURE', []))}")
print(f"RESOLUTION_FAILURE = {len(report.get('RESOLUTION_FAILURE', []))}")
print(f"PDF_TEXT_FAILURE = {len(report.get('PDF_TEXT_FAILURE', []))}")
print(f"CLASSIFICATION_UNKNOWN = {len(report.get('CLASSIFICATION_UNKNOWN', []))}")
