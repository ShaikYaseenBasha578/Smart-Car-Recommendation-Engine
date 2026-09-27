import pdfplumber
import sys

def inspect_pdf(pdf_path):
    print(f"\n--- {pdf_path} ---")
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[-6:]): # Usually at the end
            text = page.extract_text()
            if text:
                text_lower = text.lower()
                if 'addition to' in text_lower or 'features over' in text_lower:
                    print(f"Page {len(pdf.pages)-6+i}: Found 'addition to' or 'features over'")
                elif 'features' in text_lower and 'trim' in text_lower:
                    pass
                # Print sample
                print(f"Page {len(pdf.pages)-6+i} Sample: {text[:100].replace(chr(10), ' ')}")

inspect_pdf("knowledge_base/sources/oem/tata/nexon_ev/latest/brochures/nexon-ev-brochure.pdf")
inspect_pdf("knowledge_base/sources/oem/tata/tiago_ev/latest/brochures/tiago-brochure-evf-final.pdf")
