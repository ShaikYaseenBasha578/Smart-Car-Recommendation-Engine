import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Thar')
with pdfplumber.open(path) as p:
    chars = p.pages[18].chars
    for c in chars:
        if c['top'] > 70 and c['top'] < 80 and c['x0'] > 280 and c['x0'] < 310:
            print(f"Char: '{c['text']}', fontname: {c['fontname']}")
