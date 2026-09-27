def patch():
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'r') as f:
        text = f.read()
    
    text = text.replace('pdf.pages[f_idx].extract_text()', 'pdf.pages[f_idx].extract_text(layout=True)')
    text = text.replace('pdf.pages[s_idx].extract_text()', 'pdf.pages[s_idx].extract_text(layout=True)')
    
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'w') as f:
        f.write(text)
patch()
