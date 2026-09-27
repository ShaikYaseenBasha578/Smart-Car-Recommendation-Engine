import pdfplumber

pdf_path = "knowledge_base/sources/oem/hyundai/creta/gen2_facelift_2024/brochures/Hyundai_Creta_Brochure_Official.pdf"
with pdfplumber.open(pdf_path) as pdf:
    print(f"Total Pages: {len(pdf.pages)}")
    for i in range(len(pdf.pages)):
        text = pdf.pages[i].extract_text()
        if text and ("TECHNICAL SPECIFICATIONS" in text.upper() or "KEY FEATURES" in text.upper()):
            print(f"--- PAGE {i} ---")
            tables = pdf.pages[i].extract_tables()
            print(f"Tables found: {len(tables)}")
            if tables:
                print(tables[0][:5])
