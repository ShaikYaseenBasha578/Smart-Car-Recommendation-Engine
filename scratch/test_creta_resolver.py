import sqlite3
from knowledge_base.ingestion.common.resolver import SequenceMatcher

conn = sqlite3.connect("scratch/phase6_creta_dryrun.sqlite")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT name FROM variant WHERE model_id=2 AND generation_id=64")
variants = cur.fetchall()

target = "E Petrol Manual"
scores = []
for v in variants:
    s = SequenceMatcher(None, target.lower(), v['name'].lower()).ratio() * 100
    scores.append((v['name'], s))

scores.sort(key=lambda x: x[1], reverse=True)
for s in scores[:5]:
    print(s)
