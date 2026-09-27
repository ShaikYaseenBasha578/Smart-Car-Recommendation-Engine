import sys, os, pdfplumber, re, json
sys.path.append(os.getcwd())

with open("knowledge_base/sources/oem/batch_report.json") as f:
    report = json.load(f)
    
path = next(r['brochure_path'] for r in report['reports'] if r['model'] == "Dzire")

with pdfplumber.open(path) as pdf:
    for i, page in enumerate(pdf.pages):
        words = [w for w in page.extract_words() if w['x0'] >= 0 and w['x1'] <= page.width and w['top'] >= 0 and w['bottom'] <= page.height]
        
        y_bins = {}
        for w in words:
            y_q = round(w['top'] / 5) * 5
            if y_q not in y_bins: y_bins[y_q] = []
            y_bins[y_q].append(w)
            
        dense = [y for y, ws in y_bins.items() if len(ws) > 5]
        if len(dense) > 5:
            print(f"\n--- Page {i} ---")
            for y in sorted(dense)[:5]:
                row_words = sorted(y_bins[y], key=lambda x: x['x0'])
                print(f"Y={y}: {' '.join(w['text'] for w in row_words)}")
