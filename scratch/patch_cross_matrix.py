def patch():
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'r') as f:
        text = f.read()
    
    # We need to track current_engine inside extract()
    
    old_loop = """        for line in lines:
            if "Engine & trim plan" in line:
                in_engine_plan = True
                continue
            if in_engine_plan and ("Safety" in line or "Features" in line or "Exterior" in line or "Interior" in line):
                in_engine_plan = False
                in_features = True
                
            tokens = line.strip().split()
            if not tokens: continue
            
            # Engine & Trim plan assigns Powertrain to Variant
            if in_engine_plan:
                # E.g. "1.5 l MPi petrol MT ● ● ● ● ● ● ● ● -"
                checks = tokens[-len(variants):]
                if all(c in ['●', '-', 'S'] for c in checks):
                    engine_name, trans = self._parse_engine_tokens(tokens[:-len(variants)])
                    for v_idx, check in enumerate(checks):"""
                    
    new_loop = """        current_engine = ""
        for line in lines:
            if "Engine & trim plan" in line:
                in_engine_plan = True
                continue
            if in_engine_plan and ("Safety" in line or "Features" in line or "Exterior" in line or "Interior" in line):
                in_engine_plan = False
                in_features = True
                
            tokens = line.strip().split()
            if not tokens: continue
            
            if in_engine_plan:
                checks = tokens[-len(variants):]
                if len(checks) == len(variants) and all(c in ['●', '-', 'S'] for c in checks):
                    engine_name, trans = self._parse_engine_tokens(tokens[:-len(variants)])
                    if engine_name:
                        current_engine = engine_name
                    else:
                        engine_name = current_engine
                    for v_idx, check in enumerate(checks):"""
                    
    text = text.replace(old_loop, new_loop)
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'w') as f:
        f.write(text)

patch()
