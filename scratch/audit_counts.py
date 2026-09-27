import sqlite3
conn = sqlite3.connect('scratch/carrec_kb_phase8a_shadow.db')

def count(status):
    return conn.execute("SELECT COUNT(*) FROM safety_test_applicability WHERE mapping_status=?", (status,)).fetchone()[0]

exact = count('EXACT_CANONICAL_VARIANT')
unresolved = count('EXPLICIT_SOURCE_VARIANT_UNRESOLVED')
model = count('MODEL_SCOPE')
family = count('FAMILY_SCOPE')
total_explicit = exact + unresolved

print(f"Total explicit source applicability entries: {total_explicit}")
print(f"Exact canonical mappings: {exact}")
print(f"Unresolved explicit source variants: {unresolved}")
print(f"Model-level tests: {model}")
print(f"Family-level tests: {family}")
