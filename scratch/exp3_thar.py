import pdfplumber, json, sys, os
from collections import defaultdict
sys.path.append(os.getcwd())
with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)
thar_path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Thar')
with pdfplumber.open(thar_path) as p:
    page = p.pages[13] # Thar matrix is near the end, wait, I'll search it
    for pg in p.pages:
        text = pg.extract_text()
        if text and "AX Opt" in text:
            print("Found AX Opt text in standard extraction!")
            break
            
    # Manually search characters
    for pg in p.pages:
        chars = pg.chars
        text = "".join(c['text'] for c in sorted(chars, key=lambda x: (round(x['top']/2)*2, x['x0'])))
        if "AXOpt" in text or "AX" in text:
            print(f"Found in chars on page {pg.page_number}")
            # print surrounding
            idx = text.find("AX")
            if idx != -1:
                print(f"Surrounding: {text[max(0, idx-10):idx+20]}")
