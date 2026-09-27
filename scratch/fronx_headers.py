import pdfplumber

with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf") as pdf:
    # Top of the feature list
    print(pdf.pages[18].extract_text(layout=True)[:1000])
