import pdfplumber
import sys

paths = [
    "knowledge_base/sources/oem/tata/nexon/latest/brochures/nexon-ev-brochure.pdf", # Nexon ICE? The manifest says this is the path... wait!
    "knowledge_base/sources/oem/tata/nexon_ev/latest/brochures/nexon-ev-brochure.pdf",
    "knowledge_base/sources/oem/tata/tiago/latest/brochures/tiago-brochure-evf-final.pdf",
    "knowledge_base/sources/oem/tata/tiago_ev/latest/brochures/tiago-brochure-evf-final.pdf"
]

for p in paths:
    print(f"\n--- {p} ---")
    try:
        with pdfplumber.open(p) as pdf:
            for i, page in enumerate(pdf.pages[-8:]):
                text = page.extract_text()
                if not text: continue
                lines = text.split('\n')
                # Print lines containing key variant names or 'addition'
                for line in lines:
                    if 'addition to' in line.lower() or 'features over' in line.lower() or 'creative' in line.lower() or 'pure' in line.lower() or 'fearless' in line.lower() or 'smart' in line.lower():
                        print(f"Page {len(pdf.pages)-8+i}: {line.strip()}")
    except Exception as e:
        print(f"Error: {e}")
