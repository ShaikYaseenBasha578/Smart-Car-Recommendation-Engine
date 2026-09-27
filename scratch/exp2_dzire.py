import pdfplumber, json, sys, os
from collections import defaultdict
sys.path.append(os.getcwd())
with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)
dzire_path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Dzire')
with pdfplumber.open(dzire_path) as p:
    page = p.pages[4] # Matrix page
    
    # 1. extract_words()
    words = page.extract_words()
    print("Standard extract_words() excerpt:", " ".join(w['text'] for w in sorted(words, key=lambda x: x['top'])[:20]))
    
    # 2. Character level reconstruction
    chars = page.chars
    # Group by Y
    rows = defaultdict(list)
    for c in chars:
        y = round(c['top'], 1)
        rows[y].append(c)
        
    print("\nCharacter reconstruction excerpt:")
    for y in sorted(rows.keys())[:5]:
        row_chars = sorted(rows[y], key=lambda x: x['x0'])
        row_text = "".join(c['text'] for c in row_chars)
        print(f"Y={y}: {row_text}")
        
