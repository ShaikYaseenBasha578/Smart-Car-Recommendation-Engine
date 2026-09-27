import pdfplumber
import json
with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf") as pdf:
    out = {}
    for i in [16, 18, 19]: # 0-indexed feature/spec pages
        if i < len(pdf.pages):
            tables = pdf.pages[i].extract_tables()
            out[str(i)] = tables
    with open("scratch/fronx_tables.json", "w") as f:
        json.dump(out, f, indent=2)
