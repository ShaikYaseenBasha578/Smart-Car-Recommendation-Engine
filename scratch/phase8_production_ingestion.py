import sqlite3
import json
import os
import sys

import scratch.phase8a_shadow_ingestion_v4 as shadow_v4

PROD_DB = "knowledge_base/carrec_kb.db"
with open('scratch/backup_path.txt') as f:
    BACKUP_DB = f.read().strip()
RAW_JSON = "scratch/bncap_raw_results.json"

def get_pk_data(conn, table):
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        pk_col = next((row['name'] for row in cur.fetchall() if row['pk'] > 0), 'id')
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        return pk_col, {dict(r)[pk_col]: dict(r) for r in rows}
    except sqlite3.OperationalError:
        return 'id', {}

def get_db_diff(pre_conn, post_conn, tables):
    diffs = {}
    for t in tables:
        _, pre = get_pk_data(pre_conn, t)
        _, post = get_pk_data(post_conn, t)
        added = set(post.keys()) - set(pre.keys())
        deleted = set(pre.keys()) - set(post.keys())
        modified = []
        for k in set(pre.keys()) & set(post.keys()):
            pre_row = pre[k]
            post_row = post[k]
            row_diffs = {col: (pre_row[col], post_row.get(col)) 
                     for col in pre_row 
                     if pre_row[col] != post_row.get(col) and col not in ('created_at', 'acquired_at')}
            if row_diffs: modified.append((k, row_diffs))
        diffs[t] = {'added': len(added), 'deleted': len(deleted), 'modified': len(modified)}
    return diffs

def main():
    if not os.path.exists(RAW_JSON):
        print(f"ERROR: {RAW_JSON} not found. Ensure shadow pipeline produced the corpus.")
        sys.exit(1)
        
    with open(RAW_JSON) as f:
        results = json.load(f)

    print("Connecting to PROD_DB...")
    prod_conn = sqlite3.connect(PROD_DB)
    prod_conn.row_factory = sqlite3.Row
    prod_conn.execute("PRAGMA foreign_keys = ON;")
    
    pre_conn = sqlite3.connect(BACKUP_DB)
    pre_conn.row_factory = sqlite3.Row
    
    # We must create DDL before ingest. Since ingest starts a transaction, we can just run DDL now (auto-commit).
    prod_conn.execute(shadow_v4.SAFETY_TEST_DDL)
    prod_conn.execute(shadow_v4.SAFETY_APPLICABILITY_DDL)
    
    try:
        # ingest calls BEGIN TRANSACTION internally
        shadow_v4.ingest(prod_conn, results, "PRODUCTION PHASE 8")
        
        tables = [
            'manufacturer', 'model', 'generation', 'variant', 'powertrain', 
            'source', 'source_observation', 'field_provenance', 
            'safety_test', 'safety_test_applicability'
        ]
        
        diff = get_db_diff(pre_conn, prod_conn, tables)
        print("\n--- TRANSACTION INVARIANT CHECK ---")
        for t in tables:
            print(f"{t.ljust(30)} | +{diff[t]['added']} / -{diff[t]['deleted']} / ~{diff[t]['modified']}")
            
        expected = {
            'manufacturer': (0,0,0),
            'model': (0,0,0),
            'generation': (0,0,0),
            'variant': (0,0,0),
            'powertrain': (0,0,0),
            'source': (0,0,0),
            'field_provenance': (0,0,0),
            'source_observation': (37,0,0),
            'safety_test': (37,0,0),
            'safety_test_applicability': (324,0,0)
        }
        
        for t, exp in expected.items():
            act = (diff[t]['added'], diff[t]['deleted'], diff[t]['modified'])
            if act != exp:
                raise ValueError(f"INVARIANT FAILED for {t}: Expected {exp}, got {act}")
                
        bad_so = prod_conn.execute("SELECT id FROM source_observation WHERE id NOT IN (SELECT id FROM source_observation WHERE source_id=7) AND id IN (SELECT source_observation_id FROM safety_test)").fetchall()
        if bad_so:
            raise ValueError(f"INVARIANT FAILED: Found {len(bad_so)} safety_tests not pointing to source_id=7")
            
        dups = prod_conn.execute("SELECT tested_vehicle_name, COUNT(*) FROM safety_test GROUP BY tested_vehicle_name HAVING COUNT(*) > 1").fetchall()
        if dups:
            raise ValueError(f"INVARIANT FAILED: Found {len(dups)} duplicate logical safety tests")
            
        print("All invariants passed. Committing transaction.")
        prod_conn.execute("COMMIT")
        print("COMMIT SUCCESSFUL.")
        
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        # if the transaction is still active, roll it back (ingest rolls back its own if it fails inside)
        try:
            prod_conn.execute("ROLLBACK")
            print("ROLLBACK SUCCESSFUL.")
        except:
            print("Transaction already rolled back.")
        sys.exit(1)
    finally:
        prod_conn.close()
        pre_conn.close()

if __name__ == "__main__":
    main()
