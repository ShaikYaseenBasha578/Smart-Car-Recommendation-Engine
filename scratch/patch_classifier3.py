with open("knowledge_base/ingestion/oem/extractor/classifier.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "if res[0] > 10:" in line:
        new_lines.append("""                if res[0] != -1:
                    # Validate that the Bordered strategy actually extracted real headers, not just garbage symbols
                    variants = res[2]
                    valid_headers = [v.get('variant', '') for v in variants if len(v.get('variant', '')) > 1 and v.get('variant', '').lower() not in ['unknown', 'standard', 'yes', 'opt']]
                    if len(valid_headers) > 0:
                        return bordered\n""")
    else:
        new_lines.append(line)

with open("knowledge_base/ingestion/oem/extractor/classifier.py", "w") as f:
    f.writelines(new_lines)
