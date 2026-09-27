import re
import ast

def clean_key(k):
    if k is None: return ""
    k = str(k).lower().strip()
    k = re.sub(r'[^a-z0-9]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k

with open('knowledge_base/ingestion/oem/field_map_oem.py', 'r') as f:
    content = f.read()

# We want to replace OEM_FIELD_RULES definition.
# Also replace map_oem_fields definition.

new_map_oem_fields = """
def clean_key(k):
    if k is None: return ""
    k = str(k).lower().strip()
    k = re.sub(r'[^a-z0-9]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k

def map_oem_fields(raw_data):
    normalized = {}
    for k, v in raw_data.items():
        k_clean = clean_key(k)
        if k_clean in OEM_FIELD_RULES:
            can_fields, norm_func = OEM_FIELD_RULES[k_clean]
            val = norm_func(v)
            if val is not None:
                if isinstance(can_fields, tuple):
                    for cf in can_fields:
                        normalized[cf] = val
                else:
                    normalized[can_fields] = val
    return normalized
"""

# Extract the body before map_oem_fields
body_parts = content.split("def map_oem_fields(raw_data):")
prefix = body_parts[0]

# Add new mappings:
new_mappings = {
    'electronic stability control esc': ('esc', 'normalize_boolean'),
    'tyre pressure monitoring system tpms highline': ('tyre_pressure_monitoring_system', 'normalize_boolean'),
    'abs anti lock braking system with ebd': ('abs', 'normalize_boolean'),
    'vehicle stability management vsm': ('esc', 'normalize_boolean')
}

# The easiest way is to modify the dictionary block in prefix.
# First, find OEM_FIELD_RULES = {
start_idx = prefix.find("OEM_FIELD_RULES = {")
dict_block = prefix[start_idx:]
prefix = prefix[:start_idx]

# We can manually evaluate dict_block? No, it contains function references.
# We will just write out a new file by writing our own dictionary from scratch or parsing.
pass
