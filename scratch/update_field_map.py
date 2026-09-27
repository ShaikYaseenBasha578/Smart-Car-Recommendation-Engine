import re

def clean_key(k):
    if k is None: return ""
    k = k.lower().strip()
    k = re.sub(r'[^a-z0-9]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k

with open('knowledge_base/ingestion/oem/field_map_oem.py', 'r') as f:
    content = f.read()

# Replace the k.lower().strip() in map_oem_fields with clean_key
# First, insert clean_key definition before map_oem_fields
clean_def = """
import re
def clean_key(k):
    if k is None: return ""
    k = str(k).lower().strip()
    k = re.sub(r'[^a-z0-9]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k
"""
if "def clean_key" not in content:
    content = content.replace("def map_oem_fields", clean_def + "\ndef map_oem_fields")

content = content.replace("k_lower = k.lower().strip()", "k_lower = clean_key(k)")

# Now, we need to apply clean_key to ALL existing keys in OEM_FIELD_RULES
# because otherwise existing lookups will fail!
import ast
# We can just write a script to re-generate OEM_FIELD_RULES with clean_key applied to its keys.
# Actually, let's just do it dynamically in map_oem_fields:
# Instead of modifying the dict, map_oem_fields can clean the keys of OEM_FIELD_RULES on the fly.
# But better to just update the file.

