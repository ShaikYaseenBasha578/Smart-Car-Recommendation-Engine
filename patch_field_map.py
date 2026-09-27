with open("knowledge_base/ingestion/oem/field_map_oem.py", "r") as f:
    code = f.read()

new_rules = '''OEM_FIELD_RULES = {
    'length': ('length_mm', normalize_dimension),
    'total length (mm)': ('length_mm', normalize_dimension),
    'width': ('width_mm', normalize_dimension),
    'total width (mm)': ('width_mm', normalize_dimension),
    'height': ('height_mm', normalize_dimension),
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
    'airbags': ('airbags', parse_float),
    'abs': ('abs', normalize_boolean),
    'abs with ebd': ('abs', normalize_boolean),
    'esc': ('esc', normalize_boolean),
    'electronic stability program': ('esc', normalize_boolean),
    'hill hold': ('hill_assist', normalize_boolean),
    'hill hold assist': ('hill_assist', normalize_boolean)
}'''

import re
code = re.sub(r'OEM_FIELD_RULES = \{.*?\}', new_rules, code, flags=re.DOTALL)

with open("knowledge_base/ingestion/oem/field_map_oem.py", "w") as f:
    f.write(code)
