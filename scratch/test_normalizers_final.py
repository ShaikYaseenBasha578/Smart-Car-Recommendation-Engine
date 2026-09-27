from knowledge_base.ingestion.oem.field_map_oem import normalize_boolean, normalize_sunroof, map_oem_fields

test_values = [
    "YES", "TRUE", "1", "STANDARD", "yes", "true", "1", "standard",
    "NO", "FALSE", "0", "NOT AVAILABLE", "no", "false", "0", "not available",
    "-", "UNKNOWN", "N/A", None, "ambiguous text", "O", "optional"
]

print("=== NORMALIZER TEST ===")
for val in test_values:
    b = normalize_boolean(val)
    s = normalize_sunroof(val)
    print(f"Val: {repr(val)} | bool: {b} | sunroof: {repr(s)}")

print("\n=== MAP_OEM_FIELDS SEMANTICS ===")
# Test that missing canonical mapping rules yield {}
fields = [
    ("electronic stability control (esc)", "YES", {'esc': 1}),
    ("electronic stability control (esc)", "NO", {'esc': 0}),
    ("tyre pressure monitoring system(tpms) highline", "TRUE", {'tyre_pressure_monitoring_system': 1}),
    ("abs(anti-lock braking system) with ebd", "0", {'abs': 0}),
    ("vehicle stability management (vsm)", "standard", {'esc': 1}),
    ("isofix", "YES", {}),
    ("rear defogger", "YES", {})
]

for raw_k, raw_v, expected in fields:
    res = map_oem_fields({raw_k: raw_v})
    if res != expected:
        print(f"FAILED: {raw_k} : {raw_v} -> expected {expected} got {res}")
    else:
        print(f"PASS: {raw_k} : {raw_v} -> {res}")
