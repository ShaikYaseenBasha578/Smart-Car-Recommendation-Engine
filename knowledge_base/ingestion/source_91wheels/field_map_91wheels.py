import re

def safe_float(s):
    if not s: return None
    s = str(s).strip().lower()
    if s in ['na', '-', 'null', 'none', '', 'not available']: return None
    
    # Ranges: if there's a dash between numbers, we don't guess.
    if re.search(r'\d\s*-\s*\d', s): return None
        
    mult = 1.0
    if 'lakh' in s or 'lac' in s: mult = 100000.0
    elif 'cr' in s or 'crore' in s: mult = 10000000.0
    
    s = re.sub(r',', '', s)
    m = re.search(r'(\d+(\.\d+)?)', s)
    if m:
        try:
            return float(m.group(1)) * mult
        except ValueError:
            pass
    return None

def safe_bool(s):
    if s is None: return None
    s = str(s).strip().lower()
    if s in ['na', '-', 'null', 'none', '', 'not available']: return None
    if s in ['yes', 'true', '1', 'standard', 'available']: return 1
    if s in ['no', 'false', '0']: return 0
    return None

def normalize_summary_specs(specs):
    res = {}
    if not isinstance(specs, dict): return res
    
    mapping = {
        'displacement': ('engine_cc', safe_float),
        'drivetrain': ('drivetrain', lambda x: x if x else None),
        'arai_certified_mileage': ('mileage_arai_kmpl', safe_float),
        'length': ('length_mm', safe_float),
        'width': ('width_mm', safe_float),
        'height': ('height_mm', safe_float),
        'ground_clearance': ('ground_clearance_mm', safe_float),
        'seating_capacity': ('seating_capacity', lambda x: int(safe_float(x)) if safe_float(x) else None),
        'boot_space': ('boot_space_litres', safe_float),
        'tyre_pressure_monitoring_system': ('tyre_pressure_monitoring_system', safe_bool),
        'wireless_charger': ('wireless_charging', safe_bool),
        'adas': ('adas_available', safe_bool),
        'sunroof': ('sunroof', safe_bool),
        'ventilated_seats': ('ventilated_front_seats', safe_bool),
        'head_up_display': ('heads_up_display', safe_bool),
        'cruise_control': ('cruise_control', safe_bool)
    }
    
    for k, v in specs.items():
        if k in mapping:
            kb_key, func = mapping[k]
            val = func(v)
            if val is not None: res[kb_key] = val
    return res

def normalize_detailed_specs(v_specs):
    res = {}
    if not isinstance(v_specs, dict): return res
    
    mapping = {
        'engine_capacity': ('engine_cc', safe_float),
        'length': ('length_mm', safe_float),
        'width': ('width_mm', safe_float),
        'height': ('height_mm', safe_float),
        'ground_clearance': ('ground_clearance_mm', safe_float),
        'boot_space': ('boot_space_litres', safe_float),
        'seating_capacity': ('seating_capacity', lambda x: int(safe_float(x)) if safe_float(x) else None),
        'tyre_pressure_monitor': ('tyre_pressure_monitoring_system', safe_bool),
        'wireless_phone_charging': ('wireless_charging', safe_bool),
        'head_up_display': ('heads_up_display', safe_bool),
        'cruise_control': ('cruise_control', safe_bool),
        'ventilated_seats': ('ventilated_front_seats', safe_bool),
        'rain_sensing_wiper': ('rain_sensing_wiper', safe_bool),
    }
    
    for cat, items in v_specs.items():
        if not isinstance(items, dict): continue
        for k, v in items.items():
            if not isinstance(v, dict): continue
            lbl = v.get('specs_label', '').lower().replace(' ', '_')
            val = v.get('specs_value')
            
            kb_key = None
            func = None
            if k in mapping:
                kb_key, func = mapping[k]
            elif lbl in mapping:
                kb_key, func = mapping[lbl]
                
            if kb_key and func:
                parsed = func(val)
                if parsed is not None: res[kb_key] = parsed
    return res
