import re
with open('knowledge_base/ingestion/oem/field_map_oem.py', 'r') as f:
    content = f.read()

# Append this logic directly before map_oem_fields
injection = """
import re
def clean_key(k):
    if k is None: return ""
    k = str(k).lower().strip()
    k = re.sub(r'[^a-z0-9]', ' ', k)
    k = re.sub(r'\\s+', ' ', k).strip()
    return k

OEM_FIELD_RULES_CLEANED = {}
for k, v in OEM_FIELD_RULES.items():
    OEM_FIELD_RULES_CLEANED[clean_key(k)] = v

# Add missing CANONICALIZABLE mappings
OEM_FIELD_RULES_CLEANED[clean_key('electronic stability control (esc)')] = ('esc', normalize_boolean)
OEM_FIELD_RULES_CLEANED[clean_key('tyre pressure monitoring system(tpms) highline')] = ('tyre_pressure_monitoring_system', normalize_boolean)
OEM_FIELD_RULES_CLEANED[clean_key('abs(anti-lock braking system) with ebd')] = ('abs', normalize_boolean)
OEM_FIELD_RULES_CLEANED[clean_key('vehicle stability management (vsm)')] = ('esc', normalize_boolean)

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
"""

# replace map_oem_fields
body_parts = content.split("def map_oem_fields(raw_data):")
new_content = body_parts[0] + injection

with open('knowledge_base/ingestion/oem/field_map_oem.py', 'w') as f:
    f.write(new_content)

