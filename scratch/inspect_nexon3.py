import pdfplumber

pdf_path = "knowledge_base/sources/oem/tata_motors/nexon/gen2_facelift_2023/brochures/Tata_Nexon_Brochure_Official.pdf"
with pdfplumber.open(pdf_path) as pdf:
    for i in range(len(pdf.pages)):
        page = pdf.pages[i]
        text = page.extract_text()
        if text and "SMART" in text.upper() and ("FEATURES" in text.upper() or "KEY FEATURES" in text.upper()):
            print(f"--- PAGE {i} ---")
            print(text[:200])
