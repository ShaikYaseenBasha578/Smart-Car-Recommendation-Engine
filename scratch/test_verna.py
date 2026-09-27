import sys, os, pdfplumber
sys.path.append(os.getcwd())

path = "knowledge_base/sources/oem/hyundai/verna/latest/brochures/hyundai_verna_brochure.pdf"

with pdfplumber.open(path) as pdf:
    for p in pdf.pages:
        tables = p.extract_tables()
        if tables:
            for r in tables[0][:5]:
                print(r)
            break
