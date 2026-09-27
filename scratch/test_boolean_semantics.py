from knowledge_base.ingestion.oem.field_map_oem import normalize_boolean, normalize_sunroof

test_cases = [
    "yes", "true", "1", "available", "standard", 
    "no", "false", "0", "not available", "-", "unknown", 
    None, "some textual phrase", "panoramic sunroof", "[Vector:Curve]"
]

print("Value | normalize_boolean | normalize_sunroof")
print("---|---|---")
for t in test_cases:
    nb = normalize_boolean(t)
    ns = normalize_sunroof(t)
    print(f"{repr(t)} | {repr(nb)} | {repr(ns)}")
