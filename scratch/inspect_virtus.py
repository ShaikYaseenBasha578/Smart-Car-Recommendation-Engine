import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Virtus')
with pdfplumber.open(path) as p:
    words = p.pages[8].extract_words()
    print("Top words:")
    for w in sorted(words, key=lambda w: w['top'])[:30]:
        print(f"[{w['x0']:.1f}-{w['x1']:.1f}, {w['top']:.1f}] {w['text']}")
