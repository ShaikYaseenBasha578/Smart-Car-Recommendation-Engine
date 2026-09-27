import sys, os, pdfplumber
sys.path.append(os.getcwd())
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_char_utils import reconstruct_text_from_chars

dzire_path = "knowledge_base/sources/oem/maruti_suzuki/dzire/latest/brochures/maruti_suzuki_dzire_brochure.pdf"
with pdfplumber.open(dzire_path) as pdf:
    for i, page in enumerate(pdf.pages):
        recon = reconstruct_text_from_chars(page.chars)
        for r in recon['rows']:
            text = r['text'].upper()
            if "LXI" in text and "VXI" in text:
                print(f"Page {i}: {text}")
                print(f"  Blocks: {[b['text'] for b in r.get('blocks', [])]}")
