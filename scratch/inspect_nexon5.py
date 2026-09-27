import pdfplumber
with pdfplumber.open("knowledge_base/sources/oem/tata_motors/nexon/gen2_facelift_2023/brochures/Tata_Nexon_Brochure_Official.pdf") as pdf:
    for i in range(len(pdf.pages)):
        text = pdf.pages[i].extract_text()
        if text and ("AIRBAGS" in text.upper() or "TOUCHSCREEN" in text.upper()):
            print(f"--- PAGE {i} ---")
