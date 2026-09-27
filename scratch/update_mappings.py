import re
from knowledge_base.ingestion.oem.field_map_oem import clean_key, OEM_FIELD_RULES

valid_new_mappings = {
    'fully automatic climate control with max cool mode': ('automatic_climate_control', 'normalize_boolean'),
    'honda sensing adas': ('adas_available', 'normalize_boolean'),
    'adaptive cruise control': ('cruise_control', 'normalize_boolean'),
    '6 airbags system': ('airbags', 'strict_float'),
    'anti lock brake system abs': ('abs', 'normalize_boolean'),
    'vehicle stability assist vsa with electronic': ('esc', 'normalize_boolean'),
    'smartphone connectivity': ('connected_car_features', 'normalize_boolean'),
    'smartphone connectivity weblink': ('connected_car_features', 'normalize_boolean'),
    'fully automatic climate control with max cool': ('automatic_climate_control', 'normalize_boolean'),
    'adaptive cruise control lkas operation': ('cruise_control', 'normalize_boolean'),
    '7 speed paddle shifters for sequential shifts': ('paddle_shifters', 'normalize_boolean'),
    'deceleration selector paddle shifters': ('paddle_shifters', 'normalize_boolean'),
    'deceleration paddle selector shift position indicator': ('paddle_shifters', 'normalize_boolean'),
    'tyre pressure monitoring system highline': ('tyre_pressure_monitoring_system', 'normalize_boolean'),
    'hill descent control': ('hill_assist', 'normalize_boolean'),
    'ventilated seats driver co driver': ('ventilated_front_seats', 'normalize_boolean'),
    'level 2 adas': ('adas_available', 'normalize_boolean'),
    'adaptive cruise control with stop go at variant only': ('cruise_control', 'normalize_boolean'),
    'drive modes diesel zip zap zoom': ('drive_modes', 'normalize_boolean'),
    'internet connectivity': ('connected_car_features', 'normalize_boolean'),
    'auto climate control': ('automatic_climate_control', 'normalize_boolean'),
    'quadruple vertical ac vents': ('rear_ac_vents', 'normalize_boolean'),
    'anti lock braking system abs': ('abs', 'normalize_boolean'),
    'traction control system tcs': ('esc', 'normalize_boolean'),
    'hill hold control hhc': ('hill_assist', 'normalize_boolean'),
    'parking sensor at rear': ('rear_parking_sensors', 'normalize_boolean'),
    'adjustable rear ac vents': ('rear_ac_vents', 'normalize_boolean'),
    'esc electronic stability control abs antilock braking system ebd': (('esc', 'abs'), 'normalize_boolean'),
    'hhc hill hold control': ('hill_assist', 'normalize_boolean'),
    'vehicle stability control hill start assist': (('esc', 'hill_assist'), 'normalize_boolean'),
    'epb with auto hold abs with ebd': ('abs', 'normalize_boolean'),
    'front reverse parking sensor': ('rear_parking_sensors', 'normalize_boolean'),
    'paddle shifter': ('paddle_shifters', 'normalize_boolean'),
    'adjustable dual rear ac vents': ('rear_ac_vents', 'normalize_boolean'),
    'driver airbag': ('airbags', 'lambda x: 1'),
    'co driver airbag': ('airbags', 'lambda x: 2')
}

with open('knowledge_base/ingestion/oem/field_map_oem.py', 'r') as f:
    content = f.read()

# We can append these dynamically just like we did before.
injection = ""
for k, (tgt, norm) in valid_new_mappings.items():
    if isinstance(tgt, tuple):
        injection += f"OEM_FIELD_RULES_CLEANED['{k}'] = ({tgt}, {norm})\n"
    else:
        injection += f"OEM_FIELD_RULES_CLEANED['{k}'] = ('{tgt}', {norm})\n"

body_parts = content.split("def map_oem_fields(raw_data):")
new_content = body_parts[0] + injection + "\ndef map_oem_fields(raw_data):\n" + body_parts[1]

with open('knowledge_base/ingestion/oem/field_map_oem.py', 'w') as f:
    f.write(new_content)

