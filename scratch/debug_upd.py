import sqlite3
import json
from knowledge_base.ingestion.oem.field_map_oem import map_oem_fields

conn = sqlite3.connect("scratch/phase6_dryrun.sqlite")
conn.row_factory = sqlite3.Row

with open("scratch/swift_dry_run_extracted.json", "r") as f:
    payload = json.load(f)

p = payload[1] # VXi Petrol Manual
normalized = map_oem_fields(p)
print("RAW:")
for k, v in list(p.items())[:5]: print(f"  {k}: {v}")
print("NORMALIZED:")
for k, v in normalized.items():
    if v is not None:
        print(f"  {k}: {v}")
