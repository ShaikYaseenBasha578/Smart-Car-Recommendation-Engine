from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields
import sqlite3
import math

assert map_oem_fields({'max torque': '172 Nm'})['torque_nm'] == 172.0
assert map_oem_fields({'displacement': '1197 cc'})['engine_cc'] == 1197.0
assert map_oem_fields({'length': '3995 mm'})['length_mm'] == 3995.0
assert math.isclose(map_oem_fields({'max power': '100 PS'})['power_bhp'], 98.632)
assert math.isclose(map_oem_fields({'max power': '100 kW'})['power_bhp'], 134.102)

# Test SQLite storage precision
conn = sqlite3.connect(':memory:')
conn.execute("CREATE TABLE test (power_bhp REAL)")
val = map_oem_fields({'max power': '100 PS'})['power_bhp']
conn.execute("INSERT INTO test (power_bhp) VALUES (?)", (val,))
row = conn.execute("SELECT power_bhp FROM test").fetchone()
assert row[0] == val # SQLite exactly preserves the 64-bit float!

print("Precision tests passed!")
