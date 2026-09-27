with open("knowledge_base/ingestion/oem/extractor/classifier.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "return bordered" in line:
        if skip:
            skip = False # skip this one, it was the extra one
            continue
        skip = True
    new_lines.append(line)

with open("knowledge_base/ingestion/oem/extractor/classifier.py", "w") as f:
    f.writelines(new_lines)
