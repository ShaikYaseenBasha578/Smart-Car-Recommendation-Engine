import pdfplumber, json, sys, os
from PIL import Image
sys.path.append(os.getcwd())
report = json.load(open('knowledge_base/sources/oem/batch_report.json'))

# Tata Nexon EV
nexon_path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Nexon EV')
with pdfplumber.open(nexon_path) as p:
    page = p.pages[32]
    # We can't view the image easily, so we'll just check if there are Rects/Curves that might be backgrounds
    print("Nexon EV Matrix Page:")
    bg_rects = [r for r in page.rects if r['width'] > 20 and r['height'] > 20]
    print(f"Background Rects: {len(bg_rects)}")
    # Dump bounding boxes
    print([ (r['x0'], r['y0'], r['width'], r['height']) for r in bg_rects ])

# Virtus
virtus_path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Virtus')
with pdfplumber.open(virtus_path) as p:
    page = p.pages[9]
    print("\nVirtus Matrix Page:")
    bg_rects = [r for r in page.rects if r['width'] < 10 and r['height'] < 10]
    print(f"Small Rects (likely dashes): {len(bg_rects)}")
    bg_curves = [c for c in page.curves if c['width'] < 10 and c['height'] < 10]
    print(f"Small Curves (likely dots): {len(bg_curves)}")

