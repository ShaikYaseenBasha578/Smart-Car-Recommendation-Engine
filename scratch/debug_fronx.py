import pdfplumber
import re
with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf") as pdf:
    text = pdf.pages[18].extract_text(layout=True)
    for line in text.split('\n')[20:30]:
        cells = re.split(r'\s{2,}', line.strip())
        print(cells)
