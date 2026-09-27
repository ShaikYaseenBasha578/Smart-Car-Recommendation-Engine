def patch():
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'r') as f:
        text = f.read()
    
    # 1. Update _find_pages
    old1 = '"ENGINE & TRIM PLAN" in text_upper'
    new1 = '("ENGINE & TRIM PLAN" in text_upper or "ENGINE AND TRIM PLAN" in text_upper)'
    text = text.replace(old1, new1)
    
    # 2. Update loop
    old2 = '"Engine & trim plan" in line:'
    new2 = '("Engine & trim plan" in line or "Engine and trim plan" in line):'
    text = text.replace(old2, new2)
    
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'w') as f:
        f.write(text)
patch()
