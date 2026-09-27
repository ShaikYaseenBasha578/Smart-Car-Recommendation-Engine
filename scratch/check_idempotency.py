import sqlite3
import json
import os
import sys
import scratch.phase8a_shadow_ingestion_v4 as shadow_v4

# Work on a copy of the new production DB
os.system("cp knowledge_base/carrec_kb.db scratch/carrec_kb_idemp.db")

RAW_JSON = "scratch/bncap_raw_results.json"
with open(RAW_JSON) as f:
    results = json.load(f)

conn = sqlite3.connect("scratch/carrec_kb_idemp.db")
conn.row_factory = sqlite3.Row

# The ingest function returns the logical diff: a, d, m
pre = {t: shadow_v4.snapshot_table(conn, t) for t in shadow_v4.TABLES}

try:
    shadow_v4.ingest(conn, results, "PASS 2 (IDEMPOTENCY)")
except Exception as e:
    print(f"Error during pass 2: {e}")
    sys.exit(1)

post = {t: shadow_v4.snapshot_table(conn, t) for t in shadow_v4.TABLES}

print("\n--- TRUE IDEMPOTENCY PK DIFF ---")
print(f"{'table'.ljust(30)} | {'added'} | {'deleted'} | {'modified'}")
print("-" * 65)

failed = False
for t in shadow_v4.TABLES:
    a, d, m = shadow_v4.logical_diff(pre[t], post[t])
    print(f"{t.ljust(30)} | {a:<5} | {d:<7} | {m:<8}")
    if a > 0 or d > 0 or m > 0:
        failed = True

if failed:
    print("IDEMPOTENCY FAILED.")
    sys.exit(1)
else:
    print("IDEMPOTENCY SUCCESSFUL.")
