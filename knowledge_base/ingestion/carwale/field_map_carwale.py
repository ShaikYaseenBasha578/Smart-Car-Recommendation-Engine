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

def parse_version_name(name):
    """(fuel, transmission) from a CarWale version name, or None for any part not stated.
    Fuel: CNG / Hybrid (strong, 'Electric + Petrol' or e-CVT) / Electric / Diesel / Petrol ('Smart Hybrid' is a
    petrol mild hybrid). Transmission: AT / AMT / CVT / DCT / TC / MT. EVs name no gearbox; every EV in the KB is
    single-speed 'Automatic', so Electric implies AT."""
    v = ' ' + (name or '').lower() + ' '
    if 'cng' in v: fuel = 'CNG'
    elif 'electric + petrol' in v or 'strong hybrid' in v or 'e-cvt' in v: fuel = 'Hybrid'
    elif 'kwh' in v or 'electric' in v: fuel = 'Electric'
    elif 'diesel' in v: fuel = 'Diesel'
    elif 'petrol' in v: fuel = 'Petrol'
    else: fuel = None
    if 'amt' in v or re.search(r'\bags\b', v): trans = 'AMT'
    elif 'cvt' in v or 'ivt' in v: trans = 'CVT'
    elif 'dct' in v or 'dsg' in v: trans = 'DCT'
    elif '(tc)' in v or 'torque converter' in v: trans = 'TC'
    elif 'imt' in v or 'manual' in v or re.search(r'\bmt\b', v): trans = 'MT'
    elif 'automatic' in v or re.search(r'\bat\b', v): trans = 'AT'
    elif fuel == 'Electric': trans = 'AT'
    else: trans = None
    return fuel, trans

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
