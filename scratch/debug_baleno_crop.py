import pdfplumber
with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf") as pdf:
    p = pdf.pages[10]
    w = p.width
    h = p.height
    
    right_half = p.crop((w/2, 0, w, h))
    text = right_half.extract_text(layout=True)
    
    for line in text.split('\n')[:20]:
        print(line.strip())
