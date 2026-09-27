import json

with open("knowledge_base/sources/oem/batch_report.json", "r") as f:
    report = json.load(f)

print("--- METRICS ---")
print(f"GENERIC_SUCCESS = {report['summary'].get('GENERIC_SUCCESS', 0)}")
print(f"GENERIC_PARTIAL = {report['summary'].get('GENERIC_PARTIAL', 0)}")
print(f"EXTRACTION_FAILURE = {report['summary'].get('EXTRACTION_FAILURE', 0)}")
print(f"RESOLUTION_FAILURE = {report['summary'].get('RESOLUTION_FAILURE', 0)}")
print(f"PDF_TEXT_FAILURE = {report['summary'].get('PDF_TEXT_FAILURE', 0)}")
print(f"CLASSIFICATION_UNKNOWN = {report['summary'].get('CLASSIFICATION_UNKNOWN', 0)}")
