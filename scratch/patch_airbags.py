with open('knowledge_base/ingestion/oem/field_map_oem.py', 'r') as f:
    lines = f.readlines()

with open('knowledge_base/ingestion/oem/field_map_oem.py', 'w') as f:
    for line in lines:
        if "'6 airbags system'" in line:
            f.write("OEM_FIELD_RULES_CLEANED['6 airbags system'] = ('airbags', lambda x: 6 if normalize_boolean(x) == 1 else None)\n")
        else:
            f.write(line)
