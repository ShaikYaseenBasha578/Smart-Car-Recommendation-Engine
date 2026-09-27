import sqlite3

def snapshot(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tables = ['manufacturer', 'model', 'generation', 'variant', 'powertrain', 'source', 'source_observation', 'field_provenance', 'safety_test', 'safety_test_applicability']
    data = {}
    for t in tables:
        try:
            data[t] = [dict(r) for r in conn.execute(f"SELECT * FROM {t}").fetchall()]
        except sqlite3.OperationalError:
            data[t] = []
    return data

pre = snapshot('knowledge_base/carrec_kb.db')
post = snapshot('scratch/carrec_kb_phase8a_shadow.db')

for t in pre.keys():
    before = {hash(frozenset(r.items())) for r in pre[t]}
    after = {hash(frozenset(r.items())) for r in post[t]}
    added = len(after - before)
    deleted = len(before - after)
    modified = min(added, deleted) if len(pre[t]) == len(post[t]) else 0
    if modified > 0:
        added -= modified
        deleted -= modified
    print(f"{t}: +{added} added, -{deleted} deleted, ~{modified} modified")
