import sys
import os
import pdfplumber
sys.path.append(os.getcwd())
import json
with open("knowledge_base/sources/oem/batch_report.json", 'r') as f:
    report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Kushaq')
with pdfplumber.open(path) as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for t in tables:
            if any('Turbo' in str(c) for r in t for c in r):
                print(f"PAGE {i}")
                for r in t[:5]:
                    print(r)
                break
