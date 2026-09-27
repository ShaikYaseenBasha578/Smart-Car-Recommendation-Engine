import pdfplumber
import re
with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf") as pdf:
    for i, p in enumerate(pdf.pages):
        text = p.extract_text()
        if text and "FEATURE LIST" in text.upper():
            print("Found features on page", i)
