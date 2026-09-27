with open("knowledge_base/ingestion/oem/field_map_oem.py", "r") as f:
    code = f.read()

# Fix normalize_dimension
new_dim = '''def normalize_dimension(raw_str):
    if raw_str is None: return None
    s = str(raw_str).lower().strip()
    val = parse_float(s)
    if val is None: return None
    if 'cm' in s:
        return val * 10.0
    return val # Default to mm'''
code = code.replace("def normalize_dimension(raw_str):", "def normalize_dimension_old(raw_str):")
code += "\n" + new_dim

# Fix normalize_capacity
new_cap = '''def normalize_capacity(raw_str):
    if raw_str is None: return None
    s = str(raw_str).lower().strip()
    val = parse_float(s)
    return val # Default to Litres'''
code = code.replace("def normalize_capacity(raw_str):", "def normalize_capacity_old(raw_str):")
code += "\n" + new_cap

# Fix normalize_engine_cc
new_cc = '''def normalize_engine_cc(raw_str):
    if raw_str is None: return None
    s = str(raw_str).lower().strip()
    val = parse_float(s)
    if val is None: return None
    if 'l' in s or 'litre' in s:
        return val * 1000.0
    return val # Default to cc'''
code = code.replace("def normalize_engine_cc(raw_str):", "def normalize_engine_cc_old(raw_str):")
code += "\n" + new_cc

with open("knowledge_base/ingestion/oem/field_map_oem.py", "w") as f:
    f.write(code)
