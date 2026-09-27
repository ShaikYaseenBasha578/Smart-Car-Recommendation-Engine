with open("knowledge_base/ingestion/oem/field_map_oem.py", "r") as f:
    lines = f.readlines()
with open("knowledge_base/ingestion/oem/field_map_oem.py", "w") as f:
    for line in lines:
        if "'android auto & apple carplay'" in line:
            f.write("    'android auto & apple carplay': (('android_auto', 'apple_carplay'), normalize_boolean),\n")
        elif "'wireless android auto & apple carplay'" in line:
            f.write("    'wireless android auto & apple carplay': (('android_auto', 'apple_carplay'), normalize_boolean)\n")
        else:
            f.write(line)
