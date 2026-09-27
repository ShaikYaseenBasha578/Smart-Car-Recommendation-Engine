import pdfplumber
with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf") as pdf:
    print(pdf.pages[9].extract_text(layout=True)[:1000])
