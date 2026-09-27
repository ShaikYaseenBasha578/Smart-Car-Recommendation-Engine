"""
OEM Field Mapping and Numeric Unit Normalization
Maps raw OEM spec strings to KB canonical fields.
Normalizes units to derived floating-point representations without arbitrary precision loss.
"""

import re

# High-precision conventional conversion factors
PS_TO_BHP = 735.49875 / 745.69987158227022
KW_TO_BHP = 1000.0 / 745.69987158227022

def robust_parse(s, valid_units):
    s = str(s).lower().replace(',', '')
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

def strict_float(s):
    try:
        return float(str(s).replace(',', '').strip())
    except ValueError:
        return None

def normalize_power(raw_str):
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
    return None

def normalize_torque(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['nm', 'kgm'])
    if not parsed: return None
    for val, unit in parsed:
        if unit == 'nm':
            return val
        if unit == 'kgm':
            return val * 9.80665
    return None

def normalize_engine_cc(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['cc', 'cm3', 'cm³', 'l', 'litre', 'litres'])
    if not parsed:
        val = strict_float(raw_str)
        if val is not None and val > 100: # Sanity check for cc
            return val
        return None
    for val, unit in parsed:
        if unit in ['cc', 'cm3', 'cm³']:
            return val
        if unit in ['l', 'litre', 'litres']:
            return val * 1000.0
    return None

def normalize_dimension(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['mm', 'cm', 'm'])
    if not parsed:
        return strict_float(raw_str)
    for val, unit in parsed:
        if unit == 'mm': return val
        if unit == 'cm': return val * 10.0
        if unit == 'm': return val * 1000.0
    return None

def normalize_capacity(raw_str):
    if raw_str is None: return None
    parsed = robust_parse(raw_str, ['l', 'litre', 'litres'])
    if not parsed:
        return strict_float(raw_str)
    for val, unit in parsed:
        if unit in ['l', 'litre', 'litres']: return val
    return None

def normalize_boolean(raw_str):
    if raw_str is None: return None
    s = str(raw_str).lower().strip()
    if s in ['standard', 'std', 'yes', 'y', '1', '✓', 'true']:
        return 1
    if s in ['no', 'n', '0', 'not available', 'false', '-']:
        return 0
    if s in ['optional', 'available', 'n/a', 'unknown']:
        return None
    return None


def normalize_sunroof(raw_str):
    if raw_str is None: return None
    s = str(raw_str).lower().strip()
    if s in ['no', 'n', '0', 'not available', 'false', '-']: return 0
    if s in ['optional', 'available', 'n/a', 'unknown']: return None
    if s in ['standard', 'std', 'yes', 'y', '1', '✓', 'true']: return 'Standard'
    if 'panoramic' in s: return 'Panoramic'
    if 'electric' in s or 'sunroof' in s: return 'Electric'
    return s.title()

OEM_FIELD_RULES = {
    'length': ('length_mm', normalize_dimension),
    'overall length (mm)': ('length_mm', normalize_dimension),
    'total length (mm)': ('length_mm', normalize_dimension),
    'width': ('width_mm', normalize_dimension),
    'overall width (mm)': ('width_mm', normalize_dimension),
    'total width (mm)': ('width_mm', normalize_dimension),
    'height': ('height_mm', normalize_dimension),
    'overall height (mm)': ('height_mm', normalize_dimension),
    'total height (mm) (unladen)': ('height_mm', normalize_dimension),
    'wheelbase': ('wheelbase_mm', normalize_dimension),
    'wheel base (mm)': ('wheelbase_mm', normalize_dimension),
    'boot space': ('boot_space_litres', normalize_capacity),
    'boot space (l)¹': ('boot_space_litres', normalize_capacity),
    'fuel tank capacity': ('fuel_tank_litres', normalize_capacity),
    'fuel tank capacity (l)': ('fuel_tank_litres', normalize_capacity),
    'displacement': ('engine_cc', normalize_engine_cc),
    'engine capacity (cc)': ('engine_cc', normalize_engine_cc),
    'max power': ('power_bhp', normalize_power),
    'max. power': ('power_bhp', normalize_power),
    'max torque': ('torque_nm', normalize_torque),
    'max. torque': ('torque_nm', normalize_torque),
    'airbags': ('airbags', strict_float),
    'abs': ('abs', normalize_boolean),
    'abs with ebd': ('abs', normalize_boolean),
    'esc': ('esc', normalize_boolean),
    'electronic stability program': ('esc', normalize_boolean),
    'electronic stability control': ('esc', normalize_boolean),
    'electronic stability program (esp)': ('esc', normalize_boolean),
    'hill hold': ('hill_assist', normalize_boolean),
    'hill hold assist': ('hill_assist', normalize_boolean),
    'hill hold control': ('hill_assist', normalize_boolean),
    'hill start assist': ('hill_assist', normalize_boolean),
    'hill start assist control (hac)': ('hill_assist', normalize_boolean),
    'tyre pressure monitoring system': ('tyre_pressure_monitoring_system', normalize_boolean),
    'tyre pressure monitoring system (tpms)': ('tyre_pressure_monitoring_system', normalize_boolean),
    'tpms': ('tyre_pressure_monitoring_system', normalize_boolean),
    'tpms - tyre pressure monitoring system': ('tyre_pressure_monitoring_system', normalize_boolean),
    'rear parking sensors': ('rear_parking_sensors', normalize_boolean),
    'reverse parking sensors': ('rear_parking_sensors', normalize_boolean),
    'rear camera': ('rear_camera', normalize_boolean),
    'rear parking camera': ('rear_camera', normalize_boolean),
    'reverse parking camera': ('rear_camera', normalize_boolean),
    'wide-angle rear parking camera': ('rear_camera', normalize_boolean),
    'rear view camera': ('rear_camera', normalize_boolean),
    '360 degree camera': ('camera_360', normalize_boolean),
    '360 camera': ('camera_360', normalize_boolean),
    'around view monitor': ('camera_360', normalize_boolean),
    'advanced driver assistance system (adas)': ('adas_available', normalize_boolean),
    'hyundai smartsense (level 2 adas)': ('adas_available', normalize_boolean),
    'adas level 2': ('adas_available', normalize_boolean),
    'auto ac': ('automatic_climate_control', normalize_boolean),
    'automatic climate control': ('automatic_climate_control', normalize_boolean),
    'fully automatic temperature control (fatc)': ('automatic_climate_control', normalize_boolean),
    'fatc': ('automatic_climate_control', normalize_boolean),
    'rear ac vents': ('rear_ac_vents', normalize_boolean),
    'electric sunroof': ('sunroof', normalize_sunroof),
    'panoramic sunroof': ('sunroof', normalize_sunroof),
    'sunroof': ('sunroof', normalize_sunroof),
    'voice enabled smart panoramic sunroof': ('sunroof', normalize_sunroof),
    'smart panoramic sunroof': ('sunroof', normalize_sunroof),
    'ventilated seats': ('ventilated_front_seats', normalize_boolean),
    'front ventilated seats': ('ventilated_front_seats', normalize_boolean),
    'ventilated front seats': ('ventilated_front_seats', normalize_boolean),
    'cruise control': ('cruise_control', normalize_boolean),
    'paddle shifters': ('paddle_shifters', normalize_boolean),
    'wireless phone charger': ('wireless_charging', normalize_boolean),
    'wireless charger': ('wireless_charging', normalize_boolean),
    'wireless charging': ('wireless_charging', normalize_boolean),
    'heads up display': ('heads_up_display', normalize_boolean),
    'head up display': ('heads_up_display', normalize_boolean),
    'hud': ('heads_up_display', normalize_boolean),
    'drive mode select': ('drive_modes', normalize_boolean),
    'drive modes': ('drive_modes', normalize_boolean),
    'multi drive modes': ('drive_modes', normalize_boolean),
    'connected car features': ('connected_car_features', normalize_boolean),
    'connected car technology': ('connected_car_features', normalize_boolean),
    'hyundai bluelink': ('connected_car_features', normalize_boolean),
    'kia connect': ('connected_car_features', normalize_boolean),
    'suzuki connect': ('connected_car_features', normalize_boolean),
    'android auto': ('android_auto', normalize_boolean),
    'apple carplay': ('apple_carplay', normalize_boolean),
    'android auto & apple carplay': (('android_auto', 'apple_carplay'), normalize_boolean),
    'wireless android auto & apple carplay': (('android_auto', 'apple_carplay'), normalize_boolean)
}



import re
def clean_key(k):
    if k is None: return ""
    k = str(k).lower().strip()
    k = re.sub(r'[^a-z0-9]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k

OEM_FIELD_RULES_CLEANED = {}
for k, v in OEM_FIELD_RULES.items():
    OEM_FIELD_RULES_CLEANED[clean_key(k)] = v

# Add missing CANONICALIZABLE mappings
OEM_FIELD_RULES_CLEANED[clean_key('electronic stability control (esc)')] = ('esc', normalize_boolean)
OEM_FIELD_RULES_CLEANED[clean_key('tyre pressure monitoring system(tpms) highline')] = ('tyre_pressure_monitoring_system', normalize_boolean)
OEM_FIELD_RULES_CLEANED[clean_key('abs(anti-lock braking system) with ebd')] = ('abs', normalize_boolean)
OEM_FIELD_RULES_CLEANED[clean_key('vehicle stability management (vsm)')] = ('esc', normalize_boolean)

OEM_FIELD_RULES_CLEANED['fully automatic climate control with max cool mode'] = ('automatic_climate_control', normalize_boolean)
OEM_FIELD_RULES_CLEANED['honda sensing adas'] = ('adas_available', normalize_boolean)
OEM_FIELD_RULES_CLEANED['adaptive cruise control'] = ('cruise_control', normalize_boolean)
OEM_FIELD_RULES_CLEANED['6 airbags system'] = ('airbags', lambda x: 6 if normalize_boolean(x) == 1 else None)
OEM_FIELD_RULES_CLEANED['anti lock brake system abs'] = ('abs', normalize_boolean)
OEM_FIELD_RULES_CLEANED['vehicle stability assist vsa with electronic'] = ('esc', normalize_boolean)
OEM_FIELD_RULES_CLEANED['fully automatic climate control with max cool'] = ('automatic_climate_control', normalize_boolean)
OEM_FIELD_RULES_CLEANED['adaptive cruise control lkas operation'] = ('cruise_control', normalize_boolean)
OEM_FIELD_RULES_CLEANED['7 speed paddle shifters for sequential shifts'] = ('paddle_shifters', normalize_boolean)
OEM_FIELD_RULES_CLEANED['deceleration selector paddle shifters'] = ('paddle_shifters', normalize_boolean)
OEM_FIELD_RULES_CLEANED['deceleration paddle selector shift position indicator'] = ('paddle_shifters', normalize_boolean)
OEM_FIELD_RULES_CLEANED['tyre pressure monitoring system highline'] = ('tyre_pressure_monitoring_system', normalize_boolean)
OEM_FIELD_RULES_CLEANED['ventilated seats driver co driver'] = ('ventilated_front_seats', normalize_boolean)
OEM_FIELD_RULES_CLEANED['level 2 adas'] = ('adas_available', normalize_boolean)
OEM_FIELD_RULES_CLEANED['adaptive cruise control with stop go at variant only'] = ('cruise_control', normalize_boolean)
OEM_FIELD_RULES_CLEANED['drive modes diesel zip zap zoom'] = ('drive_modes', normalize_boolean)
OEM_FIELD_RULES_CLEANED['internet connectivity'] = ('connected_car_features', normalize_boolean)
OEM_FIELD_RULES_CLEANED['auto climate control'] = ('automatic_climate_control', normalize_boolean)
OEM_FIELD_RULES_CLEANED['anti lock braking system abs'] = ('abs', normalize_boolean)
OEM_FIELD_RULES_CLEANED['hill hold control hhc'] = ('hill_assist', normalize_boolean)
OEM_FIELD_RULES_CLEANED['parking sensor at rear'] = ('rear_parking_sensors', normalize_boolean)
OEM_FIELD_RULES_CLEANED['adjustable rear ac vents'] = ('rear_ac_vents', normalize_boolean)
OEM_FIELD_RULES_CLEANED['esc electronic stability control abs antilock braking system ebd'] = (('esc', 'abs'), normalize_boolean)
OEM_FIELD_RULES_CLEANED['hhc hill hold control'] = ('hill_assist', normalize_boolean)
OEM_FIELD_RULES_CLEANED['vehicle stability control hill start assist'] = (('esc', 'hill_assist'), normalize_boolean)
OEM_FIELD_RULES_CLEANED['epb with auto hold abs with ebd'] = ('abs', normalize_boolean)
OEM_FIELD_RULES_CLEANED['front reverse parking sensor'] = ('rear_parking_sensors', normalize_boolean)
OEM_FIELD_RULES_CLEANED['paddle shifter'] = ('paddle_shifters', normalize_boolean)
OEM_FIELD_RULES_CLEANED['adjustable dual rear ac vents'] = ('rear_ac_vents', normalize_boolean)


def map_oem_fields(raw_data):


    normalized = {}
    for k, v in raw_data.items():
        k_clean = clean_key(k)
        if k_clean in OEM_FIELD_RULES_CLEANED:
            can_fields, norm_func = OEM_FIELD_RULES_CLEANED[k_clean]
            val = norm_func(v)
            if val is not None:
                if isinstance(can_fields, tuple):
                    for cf in can_fields:
                        normalized[cf] = val
                else:
                    normalized[can_fields] = val
    return normalized
