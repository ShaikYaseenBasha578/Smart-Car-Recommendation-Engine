import sys, os, pdfplumber
sys.path.append(os.getcwd())

path = "knowledge_base/sources/oem/hyundai/venue/latest/brochures/hyundai_venue_brochure.pdf"

with pdfplumber.open(path) as pdf:
    tables = pdf.pages[18].extract_tables()
    if tables:
        for r in tables[0][:5]:
            print(r)
