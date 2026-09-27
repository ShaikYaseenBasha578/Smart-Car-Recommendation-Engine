import pdfplumber
import json
with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/wagon_r/latest/brochures/WagonR_Brochure.pdf") as pdf:
    out = {}
    for i in range(len(pdf.pages)):
        out[str(i)] = pdf.pages[i].extract_text()
    with open("scratch/wagonr_text.json", "w") as f:
        json.dump(out, f, indent=2)
