import re

content = ""
with open("knowledge_base/ingestion/oem/field_map_oem.py", "r") as f:
    content = f.read()

new_func = """def map_oem_fields(raw_data):
    normalized = {}
    for k, v in raw_data.items():
        k_lower = k.lower().strip()
        if k_lower in OEM_FIELD_RULES:
            can_fields, norm_func = OEM_FIELD_RULES[k_lower]
            val = norm_func(v)
            if val is not None:
                if isinstance(can_fields, tuple):
                    for cf in can_fields:
                        normalized[cf] = val
                else:
                    normalized[can_fields] = val
    return normalized"""

content = re.sub(r'def map_oem_fields.*?return normalized', new_func, content, flags=re.DOTALL)

with open("knowledge_base/ingestion/oem/field_map_oem.py", "w") as f:
    f.write(content)
print("Updated map_oem_fields func")
