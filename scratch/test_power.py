from knowledge_base.ingestion.oem.field_map_oem import normalize_power

assert round(normalize_power("60 kW"), 4) == 80.4613
assert round(normalize_power("81.58 PS"), 4) == 80.4640
assert round(normalize_power("80.46 bhp"), 4) == 80.4600
assert round(normalize_power("60 kW @5700 rpm or 81.58 PS @5700 rpm"), 4) == 80.4627
assert round(normalize_power("100 kW"), 4) == 134.1022
assert round(normalize_power("100 PS"), 4) == 98.6320
assert round(normalize_power("100 bhp"), 4) == 100.0000

assert normalize_power("100 kW or 50 PS") is None
assert normalize_power("100 hp") is None
assert normalize_power("100") is None
assert normalize_power("hello kW") is None
assert normalize_power("100 rpm") is None
assert normalize_power("100 rpm or 60 kW") is not None # Will extract 60 kW

print("Power normalization tests passed.")
