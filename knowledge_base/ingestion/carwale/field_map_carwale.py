import re

def parse_boot_space(val):
    if not val or val == 'NOT_FOUND': return None
    match = re.search(r'(\d+)\s*L', val, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def parse_bool(val):
    if not val or val == 'NOT_FOUND': return None
    v = val.lower()
    if 'no' in v and 'yes' not in v: return 0
    if 'yes' in v or 'panoramic' in v or 'electric' in v or 'adaptive' in v: return 1
    if v == '0': return 0
    if v == '1': return 1
    return None

def extract_transmission(val):
    if not val or val == 'NOT_FOUND': return None
    v = val.lower()
    if 'cvt' in v or 'continuously variable' in v: return 'CVT'
    if 'dct' in v or 'dual clutch' in v: return 'DCT'
    if 'torque converter' in v or 'tc' in v.split(): return 'Torque Converter'
    if 'amt' in v or 'automated manual' in v: return 'AMT'
    if 'imt' in v or 'clutchless manual' in v: return 'iMT'
    if 'manual' in v: return 'Manual'
    if 'automatic' in v: return 'Automatic'
    return None

def map_carwale_features(features):
    return {
        'transmission': extract_transmission(features.get('Transmission', '')),
        'sunroof': parse_bool(features.get('Sunroof', '')),
        'cruise_control': parse_bool(features.get('Cruise Control', '')),
        'adas_available': parse_bool(features.get('ADAS', '')),
        'boot_space_litres': parse_boot_space(features.get('Bootspace ', '')),
        'ventilated_front_seats': parse_bool(features.get('Ventilated Seats ', '')),
        'heads_up_display': parse_bool(features.get('Heads Up Display (HUD)', '')),
        'tyre_pressure_monitoring_system': parse_bool(features.get('Tyre Pressure Monitoring System', ''))
    }
    
def map_resolver_fields(specs_summary):
    fuel = specs_summary.get('Fuel Type')
    cc = specs_summary.get('Displacement')
    trans = extract_transmission(specs_summary.get('Transmission Type'))
    if cc:
        try:
            cc = int(cc)
        except:
            cc = None
    return fuel, cc, trans
