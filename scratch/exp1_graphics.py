import pdfplumber, json, sys, os
sys.path.append(os.getcwd())

with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)

def get_path(model):
    return next(r['brochure_path'] for r in report['reports'] if r['model'] == model)

virtus_path = get_path('Virtus')
nexon_path = get_path('Nexon EV')

print("--- VIRTUS GRAPHICS (Page 9) ---")
with pdfplumber.open(virtus_path) as p:
    page = p.pages[9]
    print(f"Rects: {len(page.rects)}")
    print(f"Curves: {len(page.curves)}")
    print(f"Lines: {len(page.lines)}")
    print(f"Images: {len(page.images)}")
    if page.curves:
        print("Sample Curves bounding boxes:", [(c['x0'], c['top'], c['width'], c['height']) for c in page.curves[:5]])
    if page.rects:
        print("Sample Rects bounding boxes:", [(r['x0'], r['top'], r['width'], r['height']) for r in page.rects[:5]])

print("\n--- NEXON EV GRAPHICS ---")
with pdfplumber.open(nexon_path) as p:
    target_page = None
    for i, page in enumerate(p.pages):
        text = page.extract_text()
        if text and "Creative" in text and "Fearless" in text and "Empowered" in text:
            target_page = page
            print(f"Found Nexon EV matrix on Page {i}")
            break
            
    if target_page:
        print(f"Rects: {len(target_page.rects)}")
        print(f"Curves: {len(target_page.curves)}")
        print(f"Lines: {len(target_page.lines)}")
        print(f"Images: {len(target_page.images)}")
        if target_page.curves:
            print("Sample Curves bounding boxes:", [(c['x0'], c['top'], c['width'], c['height']) for c in target_page.curves[:5]])
        if target_page.rects:
            print("Sample Rects bounding boxes:", [(r['x0'], r['top'], r['width'], r['height']) for r in target_page.rects[:5]])
