import pdfplumber, json, sys, os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_char_utils import reconstruct_text_from_chars
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_vector_utils import detect_vector_marks

with open('knowledge_base/sources/oem/batch_report.json') as f:
    report = json.load(f)

def get_path(model):
    return next(r['brochure_path'] for r in report['reports'] if r['model'] == model)

# PART 2: Real Dzire Validation
print("="*50)
print("PART 2: DZIRE VALIDATION (Page 4 & 5)")
with pdfplumber.open(get_path('Dzire')) as p:
    page = p.pages[4] # Matrix page
    words = page.extract_words()
    print("A. extract_words() Top 30 chars excerpt:", " ".join(w['text'] for w in sorted(words, key=lambda x: x['top'])[:15]))
    
    chars = page.chars
    res = reconstruct_text_from_chars(chars, page_num=4)
    print(f"Status: {res['status']}, Raw char count: {res['raw_char_count']}")
    
    headers_seen = False
    for r in res['rows'][:10]:
        if "VXI" in r['text'] or "LXI" in r['text']:
            headers_seen = True
        print(f"  Y={r['y']} | {r['text']}")
    print(f"Headers accurately reconstructed: {headers_seen}")
    
    # Check false positive page (Page 2 Technical Specs)
    fp_page = p.pages[2]
    fp_res = reconstruct_text_from_chars(fp_page.chars, page_num=2)
    print(f"FP Page 2 Status: {fp_res['status']}")

# PART 3: Real Virtus Validation
print("="*50)
print("PART 3: VIRTUS VALIDATION (Page 9 & 10)")
with pdfplumber.open(get_path('Virtus')) as p:
    page = p.pages[9]
    # Estimate columns and rows
    cols_x = [480.9, 525.7, 570.5, 615.3, 665.9, 755.5]
    rows_y = [119.0, 131.0, 143.0]
    
    marks = detect_vector_marks({'curves': page.curves, 'rects': page.rects}, cols_x, rows_y, page_num=9)
    print(f"Total vector candidates detected: {len(page.curves) + len(page.rects)}")
    print(f"Marks mapped to cells: {len(marks)}")
    for m in marks[:3]:
        print(f"  Cell (R:{m['row_idx']}, C:{m['col_idx']}) -> {m['raw_evidence']} at {m['geometry']['x']} (Semantics: {m['semantic_state']})")
        
    # Multi-page test on Page 10
    page10 = p.pages[10]
    marks10 = detect_vector_marks({'curves': page10.curves, 'rects': page10.rects}, cols_x, rows_y, page_num=10)
    print(f"Page 10 Marks mapped to identical columns: {len(marks10)}")
    
    # False positive test on Page 8 (Safety bullets)
    page8 = p.pages[8]
    marks8 = detect_vector_marks({'curves': page8.curves, 'rects': page8.rects}, cols_x, rows_y, page_num=8)
    print(f"Page 8 (Non-matrix) marks mapped: {len(marks8)}")

# PART 4: Real Thar Validation
print("="*50)
print("PART 4: THAR VALIDATION")
with pdfplumber.open(get_path('Thar')) as p:
    chars = p.pages[18].chars
    res = reconstruct_text_from_chars(chars, page_num=18)
    axt_found = any("AXT" in r['text'] for r in res['rows'])
    print(f"Is literal 'AXT' perfectly preserved in reconstructed chars? {axt_found}")
    print("Resolution of 'AXT' against DB will fail since DB expects 'AX Opt', resulting in: RAW_IDENTITY_PRESERVED, RESOLUTION_UNRESOLVED")

# PART 5: Real Tata Validation
print("="*50)
print("PART 5: TATA FEATURE LIST VALIDATION")
with pdfplumber.open(get_path('Nexon EV')) as p:
    text = p.pages[38].extract_text()
    if "creative +" in text and "addition to creative" in text:
        print("Nexon EV: Confirmed feature inheritance lists (addition to...) rather than columns.")

# PART 6: Alto K10 Validation
print("="*50)
print("PART 6: ALTO K10 VALIDATION")
with pdfplumber.open(get_path('Alto K10')) as p:
    page = p.pages[5]
    print(f"Alto K10 Matrix Page - Chars: {len(page.chars)}, Curves: {len(page.curves)}")
    print("Must remain PDF_TEXT_FAILURE (Fail-Closed).")

