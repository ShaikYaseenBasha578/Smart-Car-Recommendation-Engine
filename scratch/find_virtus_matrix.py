import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Virtus')
with pdfplumber.open(path) as p:
    for i, page in enumerate(p.pages):
        text = page.extract_text()
        if text and "Highline" in text and "Topline" in text:
            print(f"Page {i} has trims!")
