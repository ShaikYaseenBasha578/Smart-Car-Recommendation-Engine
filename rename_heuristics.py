with open('knowledge_base/ingestion/common/resolver.py', 'r') as f:
    code = f.read()

code = code.replace("EDITION_KEYWORDS = [", "EDITION_STRIP_HEURISTICS = [")
code = code.replace("kw in EDITION_KEYWORDS", "kw in EDITION_STRIP_HEURISTICS")

with open('knowledge_base/ingestion/common/resolver.py', 'w') as f:
    f.write(code)
