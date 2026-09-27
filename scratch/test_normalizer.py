import re

# High-precision conventional conversion factors
PS_TO_BHP = 735.49875 / 745.69987158227022
KW_TO_BHP = 1000.0 / 745.69987158227022

def robust_parse(s, valid_units):
    s = str(s).lower().replace(',', '')
    # Match numbers (including decimals) followed by optional space and a unit from valid_units
    units_pattern = '|'.join(re.escape(u) for u in valid_units)
    pattern = rf'([\d\.]+)\s*({units_pattern})\b'
    matches = re.findall(pattern, s)
    parsed = []
    for val_str, unit in matches:
        try:
            val = float(val_str)
            parsed.append((val, unit))
        except ValueError:
            pass
    return parsed

def normalize_power(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['kw', 'ps', 'bhp', 'hp'])
    if not parsed: return None
    
    # We want to return the first valid converted value, or check all valid
    for val, unit in parsed:
        if unit == 'bhp':
            return val
        elif unit == 'ps':
            return val * PS_TO_BHP
        elif unit == 'kw':
            return val * KW_TO_BHP
        # 'hp' is rejected unless bhp is present, which would have been caught
    return None

def normalize_torque(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['nm'])
    if parsed: return parsed[0][0]
    return None

def normalize_engine_cc(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['cc', 'cm3', 'cm³', 'l', 'litre', 'litres'])
    if not parsed:
        # Check if it's just a raw number if we are forced?
        # The prompt says: "Search specifically for: first-number parsing ... Do not limit the audit to the one discovered example"
        # If no unit, we shouldn't guess, unless the field literally is 'engine capacity (cc)'.
        pass
    for val, unit in parsed:
        if unit in ['cc', 'cm3', 'cm³']:
            return val
        if unit in ['l', 'litre', 'litres']:
            return val * 1000.0
    return None

def normalize_dimension(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['mm', 'cm'])
    if not parsed:
        # Often dimensions are provided without units in table columns where unit is in header (e.g., "Total Length (mm)" -> "3860")
        # In this case, we MUST parse the raw number.
        try:
            return float(str(raw_str).replace(',', '').strip())
        except ValueError:
            return None
    for val, unit in parsed:
        if unit == 'mm': return val
        if unit == 'cm': return val * 10.0
    return None

def normalize_capacity(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['l', 'litre', 'litres'])
    if not parsed:
        try:
            return float(str(raw_str).replace(',', '').strip())
        except ValueError:
            return None
    for val, unit in parsed:
        if unit in ['l', 'litre', 'litres']: return val
    return None

print("Power:", normalize_power("60 kW @5700 rpm or 81.58 PS @5700 rpm"))
print("Torque:", normalize_torque("111.7 Nm @4300 rpm"))
