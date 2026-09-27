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
            
            for r_idx, row in enumerate(clean_matrix[:5]):
                non_empty = [c for c in row if c]
                if len(non_empty) > 2:
                    print(f"Page {i}, Row {r_idx} is header candidate:", row)
                    # Also print the next row
                    if r_idx + 1 < len(clean_matrix):
                        print(f"Page {i}, Row {r_idx+1} (next):", clean_matrix[r_idx+1])
                    break
