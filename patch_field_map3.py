import re
with open("knowledge_base/ingestion/oem/field_map_oem.py", "r") as f:
    code = f.read()

# restore to before patch_field_map2
code = code.replace("def normalize_dimension_old", "def normalize_dimension")
code = code.replace("def normalize_capacity_old", "def normalize_capacity")
code = code.replace("def normalize_engine_cc_old", "def normalize_engine_cc")
code = re.sub(r'def normalize_dimension\(raw_str\).*?return None', 
    '''def normalize_dimension(raw_str):
    if raw_str is None: return None
    s = str(raw_str).lower().strip()
    val = parse_float(s)
    if val is None: return None
    if 'cm' in s:
        return val * 10.0
    return val''', code, flags=re.DOTALL)

code = re.sub(r'def normalize_capacity\(raw_str\).*?return None', 
    '''def normalize_capacity(raw_str):
    if raw_str is None: return None
    s = str(raw_str).lower().strip()
    return parse_float(s)''', code, flags=re.DOTALL)

code = re.sub(r'def normalize_engine_cc\(raw_str\).*?return None', 
    '''def normalize_engine_cc(raw_str):
    if raw_str is None: return None
    s = str(raw_str).lower().strip()
    val = parse_float(s)
    if val is None: return None
    if 'l' in s or 'litre' in s:
        return val * 1000.0
    return val''', code, flags=re.DOTALL)

# Delete anything I accidentally appended
end_idx = code.rfind("def normalize_dimension(raw_str):")
if end_idx > code.find("def map_oem_fields"):
    code = code[:end_idx]

with open("knowledge_base/ingestion/oem/field_map_oem.py", "w") as f:
    f.write(code)
