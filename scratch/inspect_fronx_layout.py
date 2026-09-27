import pdfplumber

with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf") as pdf:
    text = pdf.pages[18].extract_text(layout=True)
    print(text[:1500])
