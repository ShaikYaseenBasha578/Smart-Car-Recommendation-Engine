with open("knowledge_base/ingestion/oem/field_map_oem.py", "r") as f:
    code = f.read()

code = code.replace("['no', 'n', '0', 'not available', 'n/a', 'false']", "['no', 'n', '0', 'not available', 'false']")
code = code.replace("['optional', 'available', '-']", "['optional', 'available', '-', 'n/a', 'unknown']")

with open("knowledge_base/ingestion/oem/field_map_oem.py", "w") as f:
    f.write(code)
