import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Virtus')
with pdfplumber.open(path) as p:
    words = p.pages[9].extract_words()
    print("Words around x=300 to 500:")
    for w in sorted(words, key=lambda w: w['top'])[:50]:
        print(w['text'], end=' ')
