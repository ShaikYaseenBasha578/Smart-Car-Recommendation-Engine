import pdfplumber
import sys

virtus_path = "knowledge_base/sources/oem/volkswagen/virtus/latest/brochures/volkswagen_virtus_brochure.pdf"
with pdfplumber.open(virtus_path) as pdf:
    for page in pdf.pages[9:16]:
        text = page.extract_text()
        if text:
            print(f"Page {page.page_number} length {len(text)}")
            if "standard" in text.lower():
                print(f"FOUND 'standard': {text.lower()[text.lower().find('standard')-50:text.lower().find('standard')+50]}")
