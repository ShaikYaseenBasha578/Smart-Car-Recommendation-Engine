import pdfplumber
import json

pdf_path = "knowledge_base/sources/oem/tata_motors/nexon/gen2_facelift_2023/brochures/Tata_Nexon_Brochure_Official.pdf"
with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[39]
    tables = page.extract_tables()
    with open("scratch/nexon_tables.json", "w") as f:
        json.dump(tables, f, indent=2)
