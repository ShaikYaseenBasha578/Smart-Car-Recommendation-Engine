import pdfplumber, json, sys, os
from collections import defaultdict
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_vector_utils import detect_vector_marks

with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)

virtus_path = next(r['brochure_path'] for r in report['reports'] if r['model'] == 'Virtus')

def discover_geometry(page):
    words = page.extract_words()
    # 1. Discover headers generically (look for top row of words that are somewhat spaced out, > 400 x0)
    # Filter non-feature words
    header_cands = [w for w in words if w['top'] < 130 and w['x0'] > 450]
    
    # Cluster headers by X to find columns
    cols = []
    current_col = []
    for w in sorted(header_cands, key=lambda x: x['x0']):
        if not current_col:
            current_col.append(w)
        else:
            if w['x0'] - current_col[-1]['x1'] < 15:
                current_col.append(w)
            else:
                cols.append(current_col)
                current_col = [w]
    if current_col: cols.append(current_col)
    
    col_centers = [sum((w['x0']+w['x1'])/2 for w in c)/len(c) for c in cols]
    header_texts = [" ".join(w['text'] for w in c) for c in cols]
    
    # 2. Discover rows generically (words with x1 < 400, clustered by Y)
    row_cands = [w for w in words if w['x1'] < 400 and w['top'] > 100]
    row_dict = defaultdict(list)
    for w in row_cands:
        y = round(w['top'] / 8) * 8
        row_dict[y].append(w)
        
    row_centers = []
    row_labels = []
    for y in sorted(row_dict.keys()):
        row_centers.append(y + 4) # approx center
        r_words = sorted(row_dict[y], key=lambda x: x['x0'])
        row_labels.append(" ".join(w['text'] for w in r_words))
        
    return col_centers, header_texts, row_centers, row_labels

with pdfplumber.open(virtus_path) as p:
    print("--- VIRTUS PAGE 9 DISCOVERY ---")
    c_x, h_text, r_y, r_labels = discover_geometry(p.pages[9])
    print(f"Discovered {len(c_x)} columns: {h_text}")
    print(f"Discovered {len(r_y)} feature rows. Sample: {r_labels[:3]}")
    
    marks = detect_vector_marks({'curves': p.pages[9].curves, 'rects': p.pages[9].rects}, c_x, r_y, page_num=9)
    print(f"Total vector candidates accepted: {len(marks)}")
    for m in marks[:3]:
        print(f"  Col {m['col_idx']}, Row {m['row_idx']} -> {m['raw_evidence']} (Semantics: {m['semantic_state']})")

    print("\n--- VIRTUS PAGE 10 (MULTI-PAGE) ---")
    c_x10, h_text10, r_y10, r_labels10 = discover_geometry(p.pages[10])
    print(f"Discovered {len(c_x10)} columns on page 10. Centers: {[round(x,1) for x in c_x10]}")
    print(f"Matches Page 9 centers? {[round(x,1) for x in c_x]} == {[round(x,1) for x in c_x10]}")
    marks10 = detect_vector_marks({'curves': p.pages[10].curves, 'rects': p.pages[10].rects}, c_x10, r_y10, page_num=10)
    print(f"Page 10 Vector candidates accepted: {len(marks10)}")
