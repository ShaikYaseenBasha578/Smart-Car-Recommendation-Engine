import sys
import os
sys.path.append(os.getcwd())
import pdfplumber
pdf_path = "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"
with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if "FEATURE" in text.upper() or "SPECIFICATIONS" in text.upper():
            tables = page.extract_tables()
            if not tables: continue
            tables.sort(key=lambda t: len(t), reverse=True)
            matrix = tables[0]
            clean_matrix = []
            for row in matrix:
                clean_row = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
                if any(clean_row):
                    clean_matrix.append(clean_row)
            print("Page:", i)
            for r_idx, row in enumerate(clean_matrix[:5]):
                print(r_idx, row)
            break
