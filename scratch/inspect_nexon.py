import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Nexon EV')
with pdfplumber.open(path) as p:
    words = p.pages[8].extract_words()
    print(len(words))
    for w in words[:20]: print(w['text'], end=' ')
