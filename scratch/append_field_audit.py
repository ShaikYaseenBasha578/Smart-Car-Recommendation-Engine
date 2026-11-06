import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)), "..")))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import sqlite3

conn = open_kb(KB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute('''
    SELECT fp.field_name, fp.decision, COUNT(*) as cnt
    FROM field_provenance fp
    JOIN source_observation so ON fp.source_observation_id = so.id
    WHERE so.source_id = 1
    GROUP BY fp.field_name, fp.decision
''')

fields = {}
for row in c.fetchall():
    fname = row['field_name']
    dec = row['decision']
    cnt = row['cnt']
    if fname not in fields:
        fields[fname] = {'accepted': 0, 'confirmed': 0, 'rejected': 0}
    fields[fname][dec] = cnt

conn.close()

audit_lines = ["## Field-Level Audit", "Field | Accepted/Updated | Confirmed/Skipped | Rejected/Conflicts | Total Observations", "---|---|---|---|---"]
for fname in sorted(fields.keys()):
    f = fields[fname]
    total = sum(f.values())
    audit_lines.append(f"{fname} | {f['accepted']} | {f['confirmed']} | {f['rejected']} | {total}")

with open("knowledge_base/reports/PHASE6_OEM_PRODUCTION_INGESTION_REPORT.md", "a") as f:
    f.write("\n" + "\n".join(audit_lines) + "\n")
print("Field audit appended.")
