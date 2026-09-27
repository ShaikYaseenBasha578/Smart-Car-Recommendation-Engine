import pdfplumber, json, sys, os
from collections import defaultdict
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))

# 1. Virtus (Vector Checkmarks)
virtus_path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Virtus')
print("--- VIRTUS VECTOR PROTOTYPE ---")
with pdfplumber.open(virtus_path) as p:
    page = p.pages[9]
    words = page.extract_words()
    # Find headers (Topline, Highline, etc)
    headers = [w for w in words if w['text'] in ['Comfortline', 'Highline', 'Topline', 'Plus'] and w['top'] < 100]
    headers = sorted(headers, key=lambda x: x['x0'])
    cols = [(w['x0'] + w['x1'])/2 for w in headers]
    print(f"Detected {len(cols)} columns: {cols}")
    
    # Feature rows
    feature_words = [w for w in words if w['x1'] < 200 and w['top'] > 100]
    # Cluster feature rows
    rows = defaultdict(list)
    for w in feature_words:
        y = round(w['top'] / 8) * 8
        rows[y].append(w)
        
    print(f"Detected {len(rows)} feature rows.")
    
    # Assign checkmarks from Curves (Dots) and Rects (Dashes)
    valid_curves = [c for c in page.curves if c['width'] < 10]
    valid_rects = [r for r in page.rects if r['width'] < 10]
    
    cells = []
    for y, r_words in list(sorted(rows.items()))[:3]:
        feature_name = " ".join([w['text'] for w in sorted(r_words, key=lambda x: x['x0'])])
        y_center = y + 4
        
        for c_idx, cx in enumerate(cols):
            # Check for curve (●)
            has_curve = any(abs(c['x0'] - cx) < 15 and abs(c['top'] - y_center) < 10 for c in valid_curves)
            has_rect = any(abs(r['x0'] - cx) < 15 and abs(r['top'] - y_center) < 10 for r in valid_rects)
            
            val = 'Standard' if has_curve else ('-' if has_rect else None)
            if val:
                cells.append({
                    "column": f"Col {c_idx}",
                    "feature": feature_name,
                    "value": val,
                    "evidence": "vector"
                })
    for cell in cells:
        print(f"  {cell['feature'][:30]:<30} | {cell['column']} | {cell['value']}")


# 2. Dzire (Character Reconstruction)
dzire_path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Dzire')
print("\n--- DZIRE CHAR PROTOTYPE ---")
with pdfplumber.open(dzire_path) as p:
    page = p.pages[4]
    chars = page.chars
    rows = defaultdict(list)
    for c in chars:
        y = round(c['top'], 1)
        rows[y].append(c)
        
    for y, r_chars in list(sorted(rows.items()))[:10]:
        row_chars = sorted(r_chars, key=lambda x: x['x0'])
        text = "".join(c['text'] for c in row_chars)
        if len(text.strip()) > 3:
            print(f"Y={y}: {text}")

