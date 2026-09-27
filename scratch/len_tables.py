import sys, os, pdfplumber, json
sys.path.append(os.getcwd())
with open("knowledge_base/sources/oem/batch_report.json") as f: report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Swift')
with pdfplumber.open(path) as pdf:
    tables = pdf.pages[5].extract_tables()
    for t_idx, t in enumerate(tables):
        print(f"Table {t_idx} len: {len(t)}")
