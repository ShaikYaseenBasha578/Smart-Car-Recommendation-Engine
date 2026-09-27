import re

with open("knowledge_base/ingestion/oem/extractor/families/borderless_variant_column_matrix.py", "r") as f:
    content = f.read()

# I will just write a new file instead of regex replacing because it's easier and safer
