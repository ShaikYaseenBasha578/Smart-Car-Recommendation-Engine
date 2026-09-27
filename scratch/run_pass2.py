import sqlite3, json
from scratch.pk_diff import pk_diff, tables
import scratch.phase8a_shadow_ingestion as phase8a
import os

print("--- RUNNING PASS 2 EXACTLY ON UNCHANGED SHADOW DB ---")
os.system('cp scratch/carrec_kb_phase8a_shadow.db scratch/carrec_kb_phase8a_shadow_temp.db')
with open('scratch/bncap_raw_results.json') as f:
    results = json.load(f)

conn = sqlite3.connect('scratch/carrec_kb_phase8a_shadow_temp.db')
conn.row_factory = sqlite3.Row
phase8a.ingest(conn, results, "EXPLICIT PASS 2")

print("\n--- TRUE IDEMPOTENCY PK DIFF ---")
pk_diff('scratch/carrec_kb_phase8a_shadow.db', 'scratch/carrec_kb_phase8a_shadow_temp.db', tables)
