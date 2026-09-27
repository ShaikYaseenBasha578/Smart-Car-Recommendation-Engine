import pdfplumber
import re
with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf") as pdf:
    text = pdf.pages[10].extract_text(layout=True)
    for line in text.split('\n')[40:50]:
        print(line.strip())
