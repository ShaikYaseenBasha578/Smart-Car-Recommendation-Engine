import sys
import os
sys.path.append(os.getcwd())
import pdfplumber
pdf_path = "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        tables = page.extract_tables()
        if tables:
            tables.sort(key=lambda t: len(t), reverse=True)
            matrix = tables[0]
            clean_matrix = []
            for row in matrix:
                clean_row = [str(c).replace('\n', ' ').strip() if c else "" for c in row]
                if any(clean_row):
                    clean_matrix.append(clean_row)
            for r_idx, row in enumerate(clean_matrix[:5]):
                print(r_idx, row)
            break
