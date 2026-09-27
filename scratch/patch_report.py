import json, sys, os
sys.path.append(os.getcwd())

with open('knowledge_base/sources/oem/batch_report.json') as f:
    r = json.load(f)

counts = {
    'GENERIC_SUCCESS': len(r['GENERIC_SUCCESS']),
    'GENERIC_PARTIAL': len(r['GENERIC_PARTIAL']),
    'EXTRACTION_FAILURE': len(r['EXTRACTION_FAILURE']),
    'RESOLUTION_FAILURE': len(r['RESOLUTION_FAILURE']),
    'PDF_TEXT_FAILURE': len(r['PDF_TEXT_FAILURE']),
    'CLASSIFICATION_UNKNOWN': len(r['CLASSIFICATION_UNKNOWN'])
}

with open('knowledge_base/reports/PHASE6_OPTION_B_IMPLEMENTATION_REPORT.md', 'r') as f:
    content = f.read()

for k, v in counts.items():
    content = content.replace(f"| {k} | 5 | TBD |", f"| {k} | 5 | {v} |") if k == 'GENERIC_SUCCESS' else content
    content = content.replace(f"| {k} | 6 | TBD |", f"| {k} | 6 | {v} |") if k == 'GENERIC_PARTIAL' else content
    content = content.replace(f"| {k} | 14 | TBD |", f"| {k} | 14 | {v} |") if k == 'EXTRACTION_FAILURE' else content
    content = content.replace(f"| {k} | 23 | TBD |", f"| {k} | 23 | {v} |") if k == 'RESOLUTION_FAILURE' else content

with open('knowledge_base/reports/PHASE6_OPTION_B_IMPLEMENTATION_REPORT.md', 'w') as f:
    f.write(content)
