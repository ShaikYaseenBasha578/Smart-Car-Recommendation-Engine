import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))
nexon_path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Nexon EV')
with pdfplumber.open(nexon_path) as p:
    print(p.pages[32].extract_text())
