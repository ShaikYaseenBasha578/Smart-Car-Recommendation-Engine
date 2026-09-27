import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Tiago EV')
with pdfplumber.open(path) as p:
    for i, page in enumerate(p.pages):
        text = page.extract_text()
        if text and "Airbags" in text:
            print(f"Tiago EV Page {i}:")
            print(text[:300].replace('\n', ' '))
            break
