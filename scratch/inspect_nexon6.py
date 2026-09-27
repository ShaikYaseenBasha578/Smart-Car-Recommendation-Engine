import pdfplumber
with pdfplumber.open("knowledge_base/sources/oem/tata_motors/nexon/gen2_facelift_2023/brochures/Tata_Nexon_Brochure_Official.pdf") as pdf:
    print("--- PAGE 37 ---")
    print(pdf.pages[37].extract_text()[:500])
    print("--- PAGE 38 ---")
    print(pdf.pages[38].extract_text()[:500])
