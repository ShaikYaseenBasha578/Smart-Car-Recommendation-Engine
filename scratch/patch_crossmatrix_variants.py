def patch():
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'r') as f:
        text = f.read()
    
    # We will remove the NotImplementedError and dynamically find variants!
    old_variants_logic = """        variants = self._get_variants()
        if not variants:
            raise NotImplementedError("Variant detection not implemented dynamically; override in subclass.")
            
        lines = page_text.split('\\n')"""
        
    new_variants_logic = """        lines = page_text.split('\\n')
        variants = self._get_variants()
        if not variants:
            # Dynamically find the Variants line
            for line in lines:
                if line.strip().startswith("Variant") or line.strip().startswith("VARIANTS") or line.strip().startswith("Variants"):
                    tokens = line.strip().split()
                    # Remove the word "Variant(s)"
                    variants = tokens[1:]
                    break
        if not variants:
            raise NotImplementedError("Could not structurally discover variants and none provided.")"""
            
    text = text.replace(old_variants_logic, new_variants_logic)
    
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'w') as f:
        f.write(text)

patch()
