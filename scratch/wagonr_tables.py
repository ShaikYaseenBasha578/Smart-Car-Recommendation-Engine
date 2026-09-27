import pdfplumber
import json
import copy

def patch_chars(page):
    for c in page.chars:
        text = c.get('text', '')
        if 'cid:' in text:
            val_str = text.replace('(cid:', '').replace(')', '')
            if val_str.isdigit():
                val = int(val_str)
                if 35 <= val <= 92: c['text'] = chr(val + 30)
                elif val == 3: c['text'] = ' '
                elif val == 8: c['text'] = '&'
                elif val == 15: c['text'] = '-'
                elif val == 13: c['text'] = '('
                elif val == 17: c['text'] = ')'
                elif val == 16: c['text'] = '.'
                elif val == 18: c['text'] = '0'
                elif val == 19: c['text'] = '1'
                elif val == 20: c['text'] = '2'
                elif val == 21: c['text'] = '3'
                elif val == 22: c['text'] = '4'
                elif val == 24: c['text'] = '6'
                elif val == 28: c['text'] = '8'
                elif val == 393: c['text'] = 'S'
                
with pdfplumber.open("knowledge_base/sources/oem/maruti_suzuki/wagon_r/latest/brochures/WagonR_Brochure.pdf") as pdf:
    page = pdf.pages[4]
    patch_chars(page)
    tables = page.extract_tables()
    print(json.dumps(tables[0][:10], indent=2))
