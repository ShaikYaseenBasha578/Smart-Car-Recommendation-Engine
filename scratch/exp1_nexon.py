import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)
nexon_path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Nexon EV')
with pdfplumber.open(nexon_path) as p:
    page = p.pages[32]
    # Check text
    words = page.extract_words()
    print("Top words:", [w['text'] for w in sorted(words, key=lambda x: x['top'])[:30]])
    # Are there checkmark symbols?
    print("Found symbols:", [w['text'] for w in words if w['text'] in {'S', '●', '✓', '—', '-', '\uf0fc', '[393]', 'Y', 'N', '✔', '√'}])
