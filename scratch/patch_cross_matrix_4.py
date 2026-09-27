def patch():
    with open('knowledge_base/ingestion/oem/extractor/families/engine_trim_cross_matrix.py', 'r') as f:
        text = f.read()
    
    # Just rewrite the whole extract function correctly.
    import re
    # We will just replace the in_engine_plan logic completely.
