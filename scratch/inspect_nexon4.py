import pdfplumber
with pdfplumber.open("knowledge_base/sources/oem/tata_motors/nexon/gen2_facelift_2023/brochures/Tata_Nexon_Brochure_Official.pdf") as pdf:
    print(pdf.pages[39].extract_text())
