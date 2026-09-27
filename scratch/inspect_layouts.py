import pdfplumber
import json

def get_text(pdf_path, pages):
    with pdfplumber.open(pdf_path) as pdf:
        return [pdf.pages[p].extract_text() for p in pages if p < len(pdf.pages)]

out = {
    "WagonR": get_text("knowledge_base/sources/oem/maruti_suzuki/wagon_r/latest/brochures/WagonR_Brochure.pdf", [4, 5]),
    "i10_Nios": get_text("knowledge_base/sources/oem/hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf", [11, 12]),
    "Fronx": get_text("knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf", [16, 18, 19]),
    "Baleno": get_text("knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf", [9, 10])
}

with open("scratch/layouts.json", "w") as f:
    json.dump(out, f, indent=2)
