import pdfplumber
import json
with pdfplumber.open("knowledge_base/sources/oem/tata_motors/nexon/gen2_facelift_2023/brochures/Tata_Nexon_Brochure_Official.pdf") as pdf:
    out = {}
    for p in [37, 38, 39]:
        out[str(p)] = pdf.pages[p].extract_text()
    with open("scratch/nexon_text.json", "w") as f:
        json.dump(out, f, indent=2)
