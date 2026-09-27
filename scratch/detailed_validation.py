import sys, os, json
import pdfplumber
sys.path.append(os.getcwd())

from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_char_utils import reconstruct_text_from_chars
from knowledge_base.ingestion.oem.extractor.families.borderless_variant_column_matrix import BorderlessVariantColumnMatrixStrategy

dzire_path = "knowledge_base/sources/oem/maruti_suzuki/dzire/latest/brochures/maruti_suzuki_dzire_brochure.pdf"
virtus_path = "knowledge_base/sources/oem/volkswagen/virtus/latest/brochures/volkswagen_virtus_brochure.pdf"

print("========================================")
print("CHARACTER RECONSTRUCTION VALIDATION")
print("========================================")
try:
    with pdfplumber.open(dzire_path) as pdf:
        page = pdf.pages[3] # Or whichever page has the variants
        chars = page.chars
        print(f"Raw character count on Dzire Page {page.page_number}: {len(chars)}")
        recon = reconstruct_text_from_chars(chars)
        print(f"Status: {recon['status']}")
        print(f"Reconstructed Rows: {len(recon['rows'])}")
        
        for r in recon['rows']:
            if "LXI" in r['text'] or "VXI" in r['text'] or "ZXI" in r['text'] or "AGS" in r['text']:
                print("--- Found Scrambled Row Reconstructed ---")
                print(f"Text: {r['text']}")
                print(f"Blocks: {[b['text'] for b in r.get('blocks', [])]}")
                break
except Exception as e:
    print(f"Error in Char Recon: {e}")

print("\n========================================")
print("MULTIPAGE VALIDATION (VW VIRTUS)")
print("========================================")
try:
    with pdfplumber.open(virtus_path) as pdf:
        strategy = BorderlessVariantColumnMatrixStrategy()
        # Mock structural check since we just want to test multipage merging logic
        # Actually _discover_structure does exactly what is required
        clusters = strategy._discover_structure(pdf)
        if not clusters:
            print("No valid borderless clusters found.")
        else:
            print(f"Discovered Matrix spanning {len(clusters)} pages.")
            for p in clusters:
                print(f"\nPage {p['page_num']}:")
                print(f"  Columns Aligned: {len(p['cols'])}")
                print(f"  Column Centers: {[int(c['center']) for c in p['cols']]}")
                print(f"  Feature Rows Discovered: {len(p['features'])}")
                print(f"  Score: {p['score']}")
                # print a sample of the first feature to prove it's not duplicating
                if p['features']:
                    print(f"  First Feature: {p['features'][0]['name']}")
                    
except Exception as e:
    print(f"Error in Multipage Validation: {e}")

