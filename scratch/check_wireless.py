import sys, os, pdfplumber, json
sys.path.append(os.getcwd())
with open("knowledge_base/sources/oem/batch_report.json") as f: report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Swift')
with pdfplumber.open(path) as pdf:
    tables = pdf.pages[5].extract_tables()
    for t_idx, t in enumerate(tables):
        for r in t:
            if r and r[0] and "Wireless" in str(r[0]):
                print(f"Found in table {t_idx}")
