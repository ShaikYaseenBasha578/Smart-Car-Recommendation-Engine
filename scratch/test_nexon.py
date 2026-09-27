import sys
import os
import pdfplumber
sys.path.append(os.getcwd())
import json
with open("knowledge_base/sources/oem/batch_report.json", 'r') as f:
    report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Nexon')
with pdfplumber.open(path) as pdf:
    tables = pdf.pages[32].extract_tables()
    for t in tables:
        print(t)
