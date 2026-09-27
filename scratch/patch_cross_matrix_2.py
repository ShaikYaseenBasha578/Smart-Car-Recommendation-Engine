def patch():
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'r') as f:
        text = f.read()
    
    old_loop = """            if in_engine_plan:
                checks = tokens[-len(variants):]
                if len(checks) == len(variants) and all(c in ['●', '-', 'S'] for c in checks):
                    engine_name, trans = self._parse_engine_tokens(tokens[:-len(variants)])
                    if engine_name:
                        current_engine = engine_name
                    else:
                        engine_name = current_engine
                    for v_idx, check in enumerate(checks):"""
                    
    new_loop = """            if in_engine_plan:
                checks = tokens[-len(variants):]
                if len(checks) == len(variants) and all(c in ['●', '-', 'S'] for c in checks):
                    engine_name, trans = self._parse_engine_tokens(tokens[:-len(variants)])
                    if engine_name:
                        current_engine = engine_name
                    else:
                        engine_name = current_engine
                    for v_idx, check in enumerate(checks):
                else:
                    # Line might be just the engine name, e.g. "1.5 l MPi petrol"
                    # Just capture it and wait for the MT/AT rows.
                    engine_name, _ = self._parse_engine_tokens(tokens)
                    if engine_name: current_engine = engine_name
                    continue
                    """
                    
    text = text.replace(old_loop, new_loop)
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'w') as f:
        f.write(text)

patch()
