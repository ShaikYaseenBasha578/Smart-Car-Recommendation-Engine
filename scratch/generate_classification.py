import re
import os
import json
from collections import defaultdict

def clean_key(k):
    k = k.lower().strip()
    k = re.sub(r'[^a-z0-9]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k

# From previous audit, we know some top unmapped fields
top_unmapped = [
    'electronic stability control (esc)',
    'tyre pressure monitoring system(tpms) highline',
    'abs(anti-lock braking system) with ebd',
    'isofix',
    'keyless entry system',
    'automatic headlamps',
    'rear defogger',
    'projector headlamps',
    'black painted',
    'seatbelt reminder (all seats)',
    'rear parcel tray',
    'central locking',
    'speed sensing auto door lock',
    'impact sensing auto door unlock',
    'immobilizer',
    'burglar alarm',
    'headlamp escort function',
    'shark fin',
    'led tail lamps',
    'rear spoiler',
    'front footwell illumination',
    'emergency stop signal (ess)',
    'shark fin antenna',
    'front parking sensors',
    'driver seat height adjuster',
    'body coloured door handles',
    'rear wiper & washer',
    'driver & passenger',
    'side & curtain',
    'vehicle stability management (vsm)',
    'rear disc brakes',
    'seat belt pretensioners - driver & passenger',
    'driver anchor pretensioner',
    'height adjustable front seat belts',
    '3 point seat belts (all seats)',
    'inside door override (driver only)',
    'driver power window with auto up down and safety',
    'day and night mirror',
    'inside rear day and night mirror with telematics switches',
    'electro chromic mirror (ecm) with telematics switches',
    'rear defogger with timer',
    'driver side',
    'passenger side'
]

canonical_columns = [
    'airbags', 'abs', 'esc', 'hill_assist', 'tyre_pressure_monitoring_system',
    'rear_parking_sensors', 'rear_camera', 'camera_360', 'adas_available',
    'automatic_climate_control', 'rear_ac_vents', 'sunroof', 'ventilated_front_seats',
    'cruise_control', 'paddle_shifters', 'wireless_charging', 'heads_up_display',
    'drive_modes', 'connected_car_features', 'android_auto', 'apple_carplay'
]

with open("scratch/corpus_unmapped_field_classification.md", "w") as f:
    f.write("# CORPUS-WIDE FIELD CLASSIFICATION\n\n")
    f.write("## Canonical Schema Reference\n")
    f.write("Valid boolean/feature columns in `variant` table:\n")
    f.write(", ".join(canonical_columns) + "\n\n")
    
    f.write("## Classification of Top Unmapped Fields\n\n")
    f.write("| Raw Field | Cleaned Key | Classification | Target Field | Reason |\n")
    f.write("|---|---|---|---|---|\n")
    
    for k in top_unmapped:
        ck = clean_key(k)
        if 'electronic stability' in ck:
            cls, tgt, rsn = 'CANONICALIZABLE', 'esc', 'Direct match for Electronic Stability Control'
        elif 'tpms' in ck or 'tyre pressure' in ck:
            cls, tgt, rsn = 'CANONICALIZABLE', 'tyre_pressure_monitoring_system', 'Direct match for TPMS'
        elif 'abs' in ck:
            cls, tgt, rsn = 'CANONICALIZABLE', 'abs', 'Direct match for ABS'
        elif 'side curtain' in ck or 'driver passenger' in ck:
            cls, tgt, rsn = 'AMBIGUOUS', 'N/A', 'Context-dependent (could refer to airbags, but the key alone is just "driver & passenger" or "side & curtain")'
        elif 'isofix' in ck or 'defogger' in ck or 'headlamp' in ck or 'locking' in ck or 'wiper' in ck or 'mirror' in ck or 'seat belt' in ck or 'window' in ck or 'sensor' in ck or 'keyless' in ck or 'alarm' in ck or 'immobilizer' in ck or 'brakes' in ck or 'door lock' in ck or 'spoiler' in ck or 'antenna' in ck or 'shark fin' in ck or 'footwell' in ck or 'adjuster' in ck or 'door handle' in ck or 'tray' in ck:
            cls, tgt, rsn = 'UNSUPPORTED', 'N/A', 'Not in the canonical `variant` schema'
        elif 'vsm' in ck or 'vehicle stability' in ck:
            cls, tgt, rsn = 'CANONICALIZABLE', 'esc', 'OEM equivalent name for Electronic Stability Control (Hyundai/Kia)'
        else:
            cls, tgt, rsn = 'MARKETING_TEXT', 'N/A', 'Styling/Marketing'
            
        f.write(f"| `{k}` | `{ck}` | **{cls}** | `{tgt}` | {rsn} |\n")

print("Classification generated.")
