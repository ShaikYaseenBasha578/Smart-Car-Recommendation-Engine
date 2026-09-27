import sys
import os
import pdfplumber
sys.path.append(os.getcwd())

from knowledge_base.ingestion.oem.extractor.families.borderless_variant_column_matrix import BorderlessVariantColumnMatrixStrategy
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_char_utils import reconstruct_text_from_chars

def validate_multipage():
    print("\n--- MULTIPAGE VALIDATION (VW VIRTUS) ---")
    pdf_path = "knowledge_base/sources/oem/volkswagen/virtus/latest/brochures/virtus_brochure.pdf"
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
        
    strategy = BorderlessVariantColumnMatrixStrategy()
    with pdfplumber.open(pdf_path) as pdf:
        clusters = strategy._discover_structure(pdf)
        if not clusters:
            print("No structure discovered.")
            return
            
        print(f"Discovered {len(clusters)} valid pages forming the matrix.")
        for page_data in clusters:
            print(f"Page {page_data['page_num']}:")
            print(f"  Columns: {len(page_data['cols'])}")
            print(f"  Headers: {page_data['headers']}")
            print(f"  Feature Rows: {len(page_data['features'])}")

def validate_char_reconstruction():
    print("\n--- CHAR RECONSTRUCTION VALIDATION (MARUTI DZIRE) ---")
    pdf_path = "knowledge_base/sources/oem/maruti/dzire/latest/brochures/dzire-brand-brochure.pdf"
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
        
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[4] # Usually page 4 or 5 has the table
        chars = page.chars
        print(f"Raw character count: {len(chars)}")
        
        reconstruction = reconstruct_text_from_chars(chars)
        print(f"Status: {reconstruction['status']}")
        
        # Find the row containing "LXI" or "VXI"
        for r in reconstruction['rows']:
            if "LXI" in r['text'] or "VXI" in r['text'] or "ZXI" in r['text']:
                print("Found Header Row:")
                print(f"  Text: {r['text']}")
                print("  Blocks discovered:")
                for b in r.get('blocks', []):
                    print(f"    - {b['text']} (center: {b['x_center']:.1f})")
                break

validate_multipage()
validate_char_reconstruction()
