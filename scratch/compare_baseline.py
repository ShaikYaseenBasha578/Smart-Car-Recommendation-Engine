import json

baseline = {
    'GENERIC_SUCCESS': 5,
    'GENERIC_PARTIAL': 6,
    'EXTRACTION_FAILURE': 14,
    'RESOLUTION_FAILURE': 23,
    'PDF_TEXT_FAILURE': 12,
    'CLASSIFICATION_UNKNOWN': 2
}

try:
    with open('knowledge_base/sources/oem/batch_report.json') as f:
        r = json.load(f)
        current = {
            'GENERIC_SUCCESS': len(r['GENERIC_SUCCESS']),
            'GENERIC_PARTIAL': len(r['GENERIC_PARTIAL']),
            'EXTRACTION_FAILURE': len(r['EXTRACTION_FAILURE']),
            'RESOLUTION_FAILURE': len(r['RESOLUTION_FAILURE']),
            'PDF_TEXT_FAILURE': len(r['PDF_TEXT_FAILURE']),
            'CLASSIFICATION_UNKNOWN': len(r['CLASSIFICATION_UNKNOWN'])
        }
        print("BASELINE -> CURRENT")
        for k in baseline.keys():
            print(f"{k}: {baseline[k]} -> {current[k]}")
except Exception as e:
    print("Not ready yet.")
