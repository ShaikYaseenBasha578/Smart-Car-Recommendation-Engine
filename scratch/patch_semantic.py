with open('knowledge_base/ingestion/oem/field_map_oem.py', 'r') as f:
    lines = f.readlines()

bad_keys = [
    "'traction control system tcs'",
    "'hill descent control'",
    "'driver airbag'",
    "'co driver airbag'",
    "'smartphone connectivity'",
    "'smartphone connectivity weblink'",
    "'connectivity dongle optional'",
    "'quadruple vertical ac vents'"
]

with open('knowledge_base/ingestion/oem/field_map_oem.py', 'w') as f:
    for line in lines:
        if any(bk in line for bk in bad_keys):
            print(f"Removing: {line.strip()}")
            continue
        f.write(line)
