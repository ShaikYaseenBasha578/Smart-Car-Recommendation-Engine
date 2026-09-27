def patch():
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'r') as f:
        text = f.read()
    
    # In extract() loop
    old1 = "if len(checks) == len(variants) and all(c in ['●', '-', 'S'] for c in checks):"
    new1 = "if len(checks) == len(variants) and all(any(sym in c for sym in ['●', '-', 'S']) for c in checks):"
    text = text.replace(old1, new1)
    
    old2 = "if check == '●' or check == 'S':"
    new2 = "if '●' in check or 'S' in check:"
    text = text.replace(old2, new2)
    
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'w') as f:
        f.write(text)

patch()
