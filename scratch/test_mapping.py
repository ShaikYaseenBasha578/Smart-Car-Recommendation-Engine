from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields

test_cases = [
    # Positive tests (Deterministic canonicalizable fields)
    ({'electronic stability control (esc)': 'Standard'}, {'esc': 1}),
    ({'tyre pressure monitoring system(tpms) highline': 'Yes'}, {'tyre_pressure_monitoring_system': 1}),
    ({'abs(anti-lock braking system) with ebd': '1'}, {'abs': 1}),
    ({'vehicle stability management (vsm)': 'standard'}, {'esc': 1}),
    ({'electronic stability control (esc)': 'not available'}, {'esc': 0}),
    
    # Negative tests (Intentionally unsupported / marketing fields)
    ({'isofix': 'Standard'}, {}),
    ({'keyless entry system': 'Standard'}, {}),
    ({'automatic headlamps': 'Yes'}, {}),
    ({'rear defogger': '1'}, {}),
    ({'premium beige & black two-tone colour coordinated interiors': 'O'}, {}),
    ({'front footwell illumination': 'Standard'}, {}),
    
    # Identity fields (Should be ignored by map_oem_fields as they are handled by identity resolver? Wait, map_oem_fields processes what it's given, it shouldn't know about identity fields unless they are in OEM_FIELD_RULES)
    ({'variant_name': 'SX'}, {})
]

passed = 0
for raw, expected in test_cases:
    res = map_oem_fields(raw)
    if res == expected:
        passed += 1
    else:
        print(f"FAILED: {raw} expected {expected}, got {res}")

if passed == len(test_cases):
    print(f"ALL {passed} TESTS PASSED.")
else:
    print(f"{len(test_cases) - passed} TESTS FAILED.")
