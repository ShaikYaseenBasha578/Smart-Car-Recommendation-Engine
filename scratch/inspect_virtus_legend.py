import pdfplumber
import sys

virtus_path = "knowledge_base/sources/oem/volkswagen/virtus/latest/brochures/volkswagen_virtus_brochure.pdf"
with pdfplumber.open(virtus_path) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            if "standard" in text.lower() or "not available" in text.lower() or "-" in text:
                print(f"Page {i}: {text[:200]}")
