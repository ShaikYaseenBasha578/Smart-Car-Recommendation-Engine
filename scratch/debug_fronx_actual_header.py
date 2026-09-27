import sys
import os
sys.path.append(os.getcwd())
import pdfplumber
pdf_path = "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"
with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[18]
    tables = page.extract_tables()
    tables.sort(key=lambda t: len(t), reverse=True)
    matrix = tables[0]
    for r in matrix[:5]:
        print([c for c in r if c])
