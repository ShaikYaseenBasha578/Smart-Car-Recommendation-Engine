import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Alto K10')
with pdfplumber.open(path) as p:
    print(p.pages[5].extract_text(layout=True))
