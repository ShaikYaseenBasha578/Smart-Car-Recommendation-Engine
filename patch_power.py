with open("knowledge_base/ingestion/oem/field_map_oem.py", "r") as f:
    code = f.read()

import re

new_power = '''def normalize_power(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['kw', 'ps', 'bhp', 'hp'])
    if not parsed: 
        return None # Power always requires units to be safe
    
    conversions = []
    for val, unit in parsed:
        if unit == 'bhp':
            conversions.append(val)
        elif unit == 'ps':
            conversions.append(val * PS_TO_BHP)
        elif unit == 'kw':
            conversions.append(val * KW_TO_BHP)
        # 'hp' is rejected unless 'bhp' is present
        
    if not conversions:
        return None
        
    if len(conversions) == 1:
        return conversions[0]
        
    # Multiple representations found. Compare them!
    min_val = min(conversions)
    max_val = max(conversions)
    
    # 2.0 bhp tolerance for rounding differences (e.g. 60 kW rounded)
    if (max_val - min_val) <= 2.0:
        return sum(conversions) / len(conversions) # Return average or could return max precision
    
    # Material disagreement! Flag it by returning None or rejecting it so it requires manual review
    return None'''

code = re.sub(r'def normalize_power\(raw_str\).*?return None\n', new_power + '\n', code, flags=re.DOTALL)

with open("knowledge_base/ingestion/oem/field_map_oem.py", "w") as f:
    f.write(code)
