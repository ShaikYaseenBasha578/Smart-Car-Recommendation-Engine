import pdfplumber
import json

pdf_path = "knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf"
out = {}
with pdfplumber.open(pdf_path) as pdf:
    for i in [12, 13, 14]:
        out[str(i)] = pdf.pages[i].extract_tables()
with open("scratch/creta_tables.json", "w") as f:
    json.dump(out, f, indent=2)
