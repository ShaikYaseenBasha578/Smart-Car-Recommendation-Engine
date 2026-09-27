import re

FEATURE_MAPPING = {
    'sunroof': ['panoramic sunroof', 'electric sunroof', 'sunroof'],
    'adas_available': [
        'adas', 'adaptive cruise control', 'lane keep assist', 'lane keep & follow assist'
    ],
    'tyre_pressure_monitoring_system': ['tpms', 'tyre pressure monitoring system'],
    'wireless_charging': ['wireless charger', 'wireless charging'],
    'cruise_control': ['cruise control'],
    'ventilated_front_seats': ['ventilated front seats', 'front ventilated seats'],
    'heads_up_display': ['heads up display', 'hud']
}

def map_v3cars_features(feature_list):
    mapped = {}
    feature_text = " | ".join(f.lower() for f in feature_list)
    for field, keywords in FEATURE_MAPPING.items():
        found = False
        for kw in keywords:
            if kw in feature_text:
                found = True
                break
        mapped[field] = 1 if found else 0
    return mapped

def extract_transmission_from_name(name):
    name_lower = name.lower()
    if 'manual' in name_lower or ' mt' in name_lower:
        return 'Manual'
    if 'automatic' in name_lower or ' amt' in name_lower or ' cvt' in name_lower or ' dct' in name_lower or ' tc' in name_lower or ' at' in name_lower:
        return 'Automatic'
    return None

def extract_fuel_from_name(name):
    name_lower = name.lower()
    if 'petrol' in name_lower: return 'Petrol'
    if 'diesel' in name_lower: return 'Diesel'
    if 'cng' in name_lower: return 'CNG'
    if 'electric' in name_lower or ' ev' in name_lower: return 'Electric'
    return None

def extract_engine_cc_from_name(name):
    match = re.search(r'(\d\.\d)L', name)
    if match:
        litres = float(match.group(1))
        return int(litres * 1000)
    return None

def parse_price(price_str):
    if not price_str: return None
    try:
        clean = re.sub(r'[^\d.]', '', price_str)
        if not clean: return None
        val = float(clean)
        if 'lakh' in price_str.lower():
            return int(val * 100000)
        elif 'crore' in price_str.lower():
            return int(val * 10000000)
        return int(val)
    except:
        return None
