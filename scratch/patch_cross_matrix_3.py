def patch():
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'r') as f:
        text = f.read()
    
    old = """                    for v_idx, check in enumerate(checks):
                else:"""
    new = """                    for v_idx, check in enumerate(checks):
                        if check == '●' or check == 'S':
                            configs.append({
                                "variant": variants[v_idx],
                                "engine": engine_name,
                                "transmission": trans,
                                "features": []
                            })
                else:"""
    text = text.replace(old, new)
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'w') as f:
        f.write(text)
patch()
