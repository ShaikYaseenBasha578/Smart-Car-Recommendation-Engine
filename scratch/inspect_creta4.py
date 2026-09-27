import pdfplumber
with pdfplumber.open("knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf") as pdf:
    print(pdf.pages[14].extract_text()[:1500])
