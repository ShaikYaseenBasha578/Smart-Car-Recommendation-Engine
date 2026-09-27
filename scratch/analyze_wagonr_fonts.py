import pdfplumber
import json

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/wagon_r/latest/brochures/WagonR_Brochure.pdf"
with pdfplumber.open(pdf_path) as pdf:
    # Just grab a few chars from page 4 to see if we can decode the cid
    chars = pdf.pages[4].chars
    sample = [c for c in chars if 'cid' in c.get('text', '')][:10]
    for c in sample:
        print(c['text'], c['fontname'], c['size'])
        
    print("Normal text on page 4:")
    print(pdf.pages[4].extract_text()[-500:])
