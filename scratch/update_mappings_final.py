import re
from knowledge_base.ingestion.oem.field_map_oem import clean_key, OEM_FIELD_RULES

valid_new_mappings = {
    'connectivity dongle optional': ('connected_car_features', 'normalize_boolean')
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
