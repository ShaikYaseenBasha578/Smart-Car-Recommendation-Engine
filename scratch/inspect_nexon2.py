import json
with open("scratch/nexon_tables.json", "r") as f:
    tables = json.load(f)
for i, t in enumerate(tables):
    print(f"--- Table {i} ---")
    for row in t[:5]:
        print(row)
