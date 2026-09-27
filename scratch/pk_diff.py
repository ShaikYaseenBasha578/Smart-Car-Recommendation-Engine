import sqlite3

def get_pk_data(db_path, table):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(f"PRAGMA table_info({table})")
        pk_col = next((row['name'] for row in cur.fetchall() if row['pk'] > 0), 'id')
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        return pk_col, {dict(r)[pk_col]: dict(r) for r in rows}
    except sqlite3.OperationalError:
        return 'id', {}

def pk_diff(pre_db, post_db, tables):
    print(f"{'table'.ljust(30)} | {'added':<5} | {'deleted':<7} | {'modified':<8}")
    print("-" * 65)
    for t in tables:
        pk_col, pre = get_pk_data(pre_db, t)
        _, post = get_pk_data(post_db, t)
        added = set(post.keys()) - set(pre.keys())
        deleted = set(pre.keys()) - set(post.keys())
        modified = []
        for k in set(pre.keys()) & set(post.keys()):
            pre_row = pre[k]
            post_row = post[k]
            diffs = {col: (pre_row[col], post_row.get(col)) 
                     for col in pre_row 
                     if pre_row[col] != post_row.get(col) and col not in ('created_at', 'acquired_at')}
            if diffs: modified.append((k, diffs))
        
        print(f"{t.ljust(30)} | {len(added):<5} | {len(deleted):<7} | {len(modified):<8}")
        for pk, diff in modified:
            print(f"  Mod PK {pk}: {diff}")

tables = [
    'manufacturer', 'model', 'generation', 'variant', 'powertrain', 
    'source', 'source_observation', 'field_provenance', 
    'safety_test', 'safety_test_applicability'
]
print("--- TRUE PRIMARY-KEY DIFF (PROD vs PASS 1) ---")
pk_diff('knowledge_base/carrec_kb.db', 'scratch/carrec_kb_phase8a_shadow.db', tables)

