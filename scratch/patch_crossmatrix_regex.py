import re

def patch():
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'r') as f:
        text = f.read()
    
    # After page_text is extracted:
    old = "page_text = pdf.pages[f_idx].extract_text(layout=True)"
    new = "page_text = pdf.pages[f_idx].extract_text(layout=True)\n            import re\n            page_text = re.sub(r'●\s*\([^)]+\)', '●', page_text)"
    text = text.replace(old, new)
    
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'w') as f:
        f.write(text)

patch()
