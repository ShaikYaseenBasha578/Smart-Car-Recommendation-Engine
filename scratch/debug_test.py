import sqlite3
import sys
import os
sys.path.append(os.getcwd())
from knowledge_base.ingestion.common.resolver import resolve_variant

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.execute("CREATE TABLE model (id INTEGER PRIMARY KEY, manufacturer_id INTEGER, name TEXT)")
conn.execute("CREATE TABLE manufacturer (id INTEGER PRIMARY KEY, name TEXT)")
conn.execute("CREATE TABLE powertrain (id INTEGER PRIMARY KEY, model_id INTEGER, fuel_type TEXT, engine_cc REAL, power_bhp REAL)")
conn.execute("CREATE TABLE variant (id INTEGER PRIMARY KEY, model_id INTEGER, generation_id INTEGER, powertrain_id INTEGER, name TEXT, full_name TEXT, transmission TEXT, drivetrain TEXT, is_discontinued INTEGER, price_ex_showroom REAL, base_variant_id INTEGER, edition_classification TEXT)")
conn.execute("CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT)")
conn.execute("CREATE TABLE variant_alias (id INTEGER, variant_id INTEGER, source_id INTEGER, alias_name TEXT, needs_review INTEGER, is_verified INTEGER)")

conn.execute("INSERT INTO source VALUES (1, '91wheels')")
conn.execute("INSERT INTO manufacturer VALUES (1, 'Hyundai')")
conn.execute("INSERT INTO model VALUES (1, 1, 'Creta')")
conn.execute("INSERT INTO powertrain VALUES (1, 1, 'Petrol', 1497, 113)")
conn.execute("INSERT INTO powertrain VALUES (2, 1, 'Diesel', 1493, 114)")
conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (1, 1, 1, 'E Petrol MT', 'Manual')")
conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (2, 1, 2, 'E Diesel MT', 'Manual')")
conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission) VALUES (3, 1, 1, 'EX Petrol MT', 'Manual')")

# Editions
conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission, base_variant_id) VALUES (4, 1, 1, 'E Dark Edition Petrol MT', 'Manual', 1)")
conn.execute("INSERT INTO variant (id, model_id, powertrain_id, name, transmission, base_variant_id) VALUES (5, 1, 1, 'E Knight Edition Petrol MT', 'Manual', 1)")

print("Resolving edition='Dark Edition'...")
print(resolve_variant(conn, 'hyundai', 'creta', 'E', 'e', 'Petrol', 'Manual', 1497, None, edition="Dark Edition"))
print("Resolving edition='Knight Edition'...")
print(resolve_variant(conn, 'hyundai', 'creta', 'E', 'e', 'Petrol', 'Manual', 1497, None, edition="Knight Edition"))

