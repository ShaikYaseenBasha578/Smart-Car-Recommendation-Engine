import pdfplumber
with pdfplumber.open("knowledge_base/sources/oem/hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf") as pdf:
    print(pdf.pages[9].extract_text()[:1000])
