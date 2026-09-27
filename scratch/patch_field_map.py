import re

content = ""
with open("knowledge_base/ingestion/oem/field_map_oem.py", "r") as f:
    content = f.read()

new_mappings = """
def normalize_sunroof(raw_str):
    if raw_str is None: return None
    s = str(raw_str).lower().strip()
    if s in ['no', 'n', '0', 'not available', 'false', '-']: return None # Treat 'no' as None to avoid overriding with literal 'no' if we just want to flag existence
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
    'android auto & apple carplay': ('android_auto', normalize_boolean), # Will only map one of them if we do 1:1, but that's a limitation we can accept or handle later
    'wireless android auto & apple carplay': ('android_auto', normalize_boolean)
}
"""

content = re.sub(r'OEM_FIELD_RULES\s*=\s*\{.*?\}', new_mappings, content, flags=re.DOTALL)

with open("knowledge_base/ingestion/oem/field_map_oem.py", "w") as f:
    f.write(content)
print("Updated field_map_oem.py")
