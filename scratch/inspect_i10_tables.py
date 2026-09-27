import pdfplumber
import json
with pdfplumber.open("knowledge_base/sources/oem/hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf") as pdf:
    out = {}
    for i in range(len(pdf.pages)):
        tables = pdf.pages[i].extract_tables()
        if tables:
            out[str(i)] = tables
    with open("scratch/i10_tables.json", "w") as f:
        json.dump(out, f, indent=2)
