import pdfplumber

with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf") as pdf:
    p = pdf.pages[18]
    w = p.width
    h = p.height
    
    right_half = p.crop((w/2, 0, w, h))
    text = right_half.extract_text(layout=True)
    
    for line in text.split('\n')[10:20]:
        print(line.strip())
