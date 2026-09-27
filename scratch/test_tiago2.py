import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Tiago')
with pdfplumber.open(path) as p:
    text = p.pages[-1].extract_text() or p.pages[-2].extract_text()
    print("TIAGO:")
    print(text[:300].replace('\n', ' '))
