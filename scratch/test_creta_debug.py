import pdfplumber
with pdfplumber.open("knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf") as pdf:
    lines12 = pdf.pages[12].extract_text().split('\n')
    for line in lines12[:15]:
        print(repr(line))
