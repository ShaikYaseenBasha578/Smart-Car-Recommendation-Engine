import sys, os, pdfplumber, json
sys.path.append(os.getcwd())
with open("knowledge_base/sources/oem/batch_report.json") as f: report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Swift')
with pdfplumber.open(path) as pdf:
    for i, p in enumerate(pdf.pages):
        tables = p.extract_tables()
        if tables:
            print(f"PAGE {i} max_cols {max([len(r) for r in tables[0]], default=0)}")
