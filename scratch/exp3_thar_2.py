import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Thar')
with pdfplumber.open(path) as p:
    words = p.pages[18].extract_words() # 0-indexed page 19
    for w in sorted(words, key=lambda w: w['top'])[:20]:
        print(f"[{w['x0']:.1f}-{w['x1']:.1f}, {w['top']:.1f}] {w['text']}")
