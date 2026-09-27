import sqlite3, json, os, sys, hashlib, shutil
from collections import defaultdict

PROD_DB = "knowledge_base/carrec_kb.db"
BACKUP_DB = "knowledge_base/backups/carrec_kb_phase8b_backup.db"
ISOLATED_DB = "scratch/carrec_kb_phase8b_isolated.db"
RAW_JSON = "scratch/bncap_raw_results.json"
RESULTS_JSON = "scratch/phase8b_results.json"
EXPECTED_CHECKSUM = "e752ebde5b7f227140bedb319c6b9753a3fdbdde"
BNCAP_SOURCE_ID = 7

BNCAP_ALIAS_TABLE = {
    'tata-safari-harrier': {'manufacturer_id': 10, 'model_ids': [30, None], 'scope': 'FAMILY_LEVEL', 'justification': 'BNCAP page explicitly covers Harrier AND Safari as one test (shared platform).'},
    'tata-punch-ev': {'manufacturer_id': 10, 'model_ids': [59], 'scope': 'MODEL_LEVEL', 'justification': 'BNCAP title is TATA PUNCH.EV. Unambiguous.'},
    'tata-punch-ev-2026': {'manufacturer_id': 10, 'model_ids': [59], 'scope': 'MODEL_LEVEL', 'justification': 'BNCAP page states updated model introduced in Feb 2026. Same CarRec model 59.'},
    'tata-nexon-ev': {'manufacturer_id': 10, 'model_ids': [6], 'scope': 'MODEL_LEVEL', 'justification': 'Unambiguous mapping to Nexon EV (model_id=6).'},
    'maruti-baleno-gasoline-2-airbags': {'manufacturer_id': 6, 'model_ids': [15], 'scope': 'MODEL_LEVEL', 'justification': 'Explicitly tested Baleno with 2 airbags. CarRec model 15.'},
    'maruti-baleno-gasoline-6-airbags': {'manufacturer_id': 6, 'model_ids': [15], 'scope': 'MODEL_LEVEL', 'justification': 'Explicitly tested Baleno with 6 airbags. CarRec model 15.'},
    'maruti-suzuki-invicto': {'manufacturer_id': None, 'model_ids': [], 'scope': 'NO_MATCH', 'justification': 'Invicto is not in CarRec top-62. Not aliasing to Innova Hycross as test is badge-specific.'},
    'nissan-tekton': {'manufacturer_id': None, 'model_ids': [], 'scope': 'NO_MATCH', 'justification': 'Nissan Tekton is not in CarRec top-62 models.'},
    'skoda-kylaq': {'manufacturer_id': 9, 'model_ids': [52], 'scope': 'MODEL_LEVEL', 'justification': 'Unambiguous mapping to Skoda Kylaq.'}
}

def resolve_entity(url_slug, title, conn):
    import re
    if url_slug in BNCAP_ALIAS_TABLE:
        alias = BNCAP_ALIAS_TABLE[url_slug]
        return ('NO_MATCH' if alias['scope'] == 'NO_MATCH' else 'RESOLVED',
                alias['scope'], alias['manufacturer_id'], alias['model_ids'], None, alias['justification'])

    t_clean = title.lower().replace('–', ' ').replace('-', ' ').replace('.', ' ').strip()
    t_nospace = re.sub(r'\s+', '', t_clean)

    makes = conn.execute("SELECT id, name FROM manufacturer").fetchall()
    best_make_id, best_make_name = None, None
    for mk in makes:
        mk_slug = re.sub(r'\s+', '', mk['name'].lower())
        if mk_slug in t_nospace:
            best_make_id = mk['id']
            best_make_name = mk['name']
            break

    if best_make_id is None:
        return 'UNRESOLVED', 'UNRESOLVED', None, [], None, f'Could not identify manufacturer from title: "{title}"'

    models = conn.execute("SELECT id, name FROM model WHERE manufacturer_id=?", (best_make_id,)).fetchall()
    matched_models = []
    for m in models:
        m_slug = re.sub(r'[\s\-.]', '', m['name'].lower())
        if m_slug in t_nospace:
            matched_models.append(m['id'])

    if len(matched_models) == 1:
        model_id = matched_models[0]
        gen = conn.execute("SELECT id FROM generation WHERE model_id=?", (model_id,)).fetchone()
        gen_id = gen['id'] if gen else None
        return 'RESOLVED', 'MODEL_LEVEL', best_make_id, [model_id], gen_id, f'Matched manufacturer and model systematically.'

    if len(matched_models) > 1:
        return 'UNRESOLVED', 'UNRESOLVED', best_make_id, matched_models, None, f'Multiple model matches: {matched_models}.'

    return 'NO_MATCH', 'UNRESOLVED', best_make_id, [], None, f'No matching model found in CarRec top-62 for {best_make_name}.'

SAFETY_TEST_DDL = """
CREATE TABLE IF NOT EXISTS safety_test (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id             INTEGER NOT NULL REFERENCES source(id),
    source_observation_id INTEGER REFERENCES source_observation(id),
    tested_vehicle_name   TEXT NOT NULL,
    tested_variant_config TEXT,
    body_type             TEXT,
    crash_test_weight_kg  TEXT,
    year_of_publication   INTEGER,
    test_period           TEXT,
    protocol_version      TEXT,
    aop_score             REAL,
    aop_stars             INTEGER,
    cop_score             REAL,
    cop_stars             INTEGER,
    sat_summary           TEXT,
    factsheet_url         TEXT,
    raw_source_url        TEXT NOT NULL UNIQUE,
    artifact_path         TEXT,
    artifact_checksum     TEXT,
    resolution_status     TEXT NOT NULL,
    applicability_notes   TEXT,
    resolution_justification TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

SAFETY_APPLICABILITY_DDL = """
CREATE TABLE IF NOT EXISTS safety_test_applicability (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    safety_test_id    INTEGER NOT NULL REFERENCES safety_test(id),
    manufacturer_id   INTEGER REFERENCES manufacturer(id),
    model_id          INTEGER REFERENCES model(id),
    generation_id     INTEGER REFERENCES generation(id),
    variant_id        INTEGER REFERENCES variant(id),
    match_confidence  TEXT NOT NULL,
    notes             TEXT,
    UNIQUE(safety_test_id, model_id, match_confidence)
)
"""

def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk: break
            h.update(chunk)
    return h.hexdigest()

def integrity(db_path):
    conn = sqlite3.connect(db_path)
    res = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    return res

def table_exists(conn, table):
    return conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0] > 0

def get_row_counts(conn, tables):
    counts = {}
    for t in tables:
        if table_exists(conn, t):
            counts[t] = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        else:
            counts[t] = 0
    return counts

def snapshot_table(conn, table):
    if not table_exists(conn, table):
        return []
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(r) for r in rows]

def logical_diff(before, after):
    b_set = {hash(frozenset(r.items())) for r in before}
    a_set = {hash(frozenset(r.items())) for r in after}
    added = len(a_set - b_set)
    deleted = len(b_set - a_set)
    modified = min(added, deleted) if len(before) == len(after) else 0
    if modified > 0:
        added -= modified
        deleted -= modified
    return added, deleted, modified

TABLES = [
    'manufacturer', 'model', 'generation', 'variant', 'powertrain',
    'source', 'source_observation', 'field_provenance',
    'safety_test', 'safety_test_applicability'
]

def ingest(conn, results, tables):
    conn.execute(SAFETY_TEST_DDL)
    conn.execute(SAFETY_APPLICABILITY_DDL)
    stats = defaultdict(int)
    
    try:
        conn.execute("BEGIN TRANSACTION")
        for res in results:
            url = res['url']
            url_slug = url.rstrip('/').split('/')[-1]
            title = res.get('tested_vehicle_name') or url_slug

            res_status, scope, make_id, model_ids, gen_id, justification = resolve_entity(url_slug, title, conn)
            stats[res_status] += 1

            # Insert source_observation ONLY IF NOT EXISTS
            so_id = None
            existing_so = conn.execute("SELECT id FROM source_observation WHERE source_url=?", (url,)).fetchone()
            if not existing_so:
                raw_payload = json.dumps({k: v for k, v in res.items() if k != 'url'})
                conn.execute("""
                    INSERT INTO source_observation
                    (source_id, raw_name, raw_payload, source_url, extraction_method, resolution_status)
                    VALUES (?, ?, ?, ?, 'html_scrape', ?)
                """, (BNCAP_SOURCE_ID, title, raw_payload, url, res_status))
                so_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            else:
                so_id = existing_so['id']

            # Insert safety_test ONLY IF NOT EXISTS
            existing_st = conn.execute("SELECT id FROM safety_test WHERE raw_source_url=?", (url,)).fetchone()
            if not existing_st:
                conn.execute("""
                    INSERT INTO safety_test (
                        source_id, source_observation_id, tested_vehicle_name, tested_variant_config,
                        body_type, crash_test_weight_kg, year_of_publication, test_period, protocol_version,
                        aop_score, aop_stars, cop_score, cop_stars, sat_summary, factsheet_url, raw_source_url,
                        artifact_path, artifact_checksum, resolution_status, applicability_notes, resolution_justification
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    BNCAP_SOURCE_ID, so_id, title, res.get('tested_variant_config'), res.get('body_type'),
                    res.get('crash_test_weight_kg'), res.get('year_of_publication'), res.get('test_period'),
                    res.get('protocol_version'), res.get('aop_score'), res.get('aop_stars'), res.get('cop_score'),
                    res.get('cop_stars'), res.get('sat_summary'), res.get('factsheet_url'), url,
                    res.get('artifact_path'), res.get('artifact_checksum'), res_status, res.get('applicability_notes'),
                    justification
                ))
                st_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            else:
                st_id = existing_st['id']

            # Insert applicability ONLY IF NOT EXISTS
            if res_status in ('RESOLVED', 'FAMILY_LEVEL') and model_ids and st_id:
                for mid in model_ids:
                    if mid is None: continue
                    existing_sa = conn.execute(
                        "SELECT id FROM safety_test_applicability WHERE safety_test_id=? AND model_id=? AND match_confidence=?",
                        (st_id, mid, scope)
                    ).fetchone()
                    if not existing_sa:
                        conn.execute("""
                            INSERT INTO safety_test_applicability
                            (safety_test_id, manufacturer_id, model_id, generation_id, variant_id, match_confidence, notes)
                            VALUES (?, ?, ?, ?, NULL, ?, ?)
                        """, (st_id, make_id, mid, gen_id if scope == 'MODEL_LEVEL' else None, scope, justification))
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        raise e
    
    return dict(stats)

def main():
    if sha1(PROD_DB) != EXPECTED_CHECKSUM:
        print(f"FAIL: Pre-run checksum doesn't match {EXPECTED_CHECKSUM} (Got {sha1(PROD_DB)})")
        sys.exit(1)
        
    with open(RAW_JSON) as f:
        results = json.load(f)

    # 1. Capture BEFORE snapshot
    conn = sqlite3.connect(PROD_DB, isolation_level=None)
    
    conn.row_factory = sqlite3.Row
    pre_counts = get_row_counts(conn, TABLES)
    pre_snap = {t: snapshot_table(conn, t) for t in TABLES}
    
    # 2. RUN INGESTION
    print("Running ingestion on PROD_DB...")
    stats = ingest(conn, results, TABLES)
    
    # 3. Capture AFTER snapshot
    post_counts = get_row_counts(conn, TABLES)
    post_snap = {t: snapshot_table(conn, t) for t in TABLES}
    
    diffs = {}
    for t in TABLES:
        a, d, m = logical_diff(pre_snap[t], post_snap[t])
        diffs[t] = {'added': a, 'deleted': d, 'modified': m}
    
    # Checkpoint before getting final cksum
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    
    post_cksum = sha1(PROD_DB)
    post_integ = integrity(PROD_DB)
    
    # 4. IDEMPOTENCY CHECK
    if os.path.exists(ISOLATED_DB): os.remove(ISOLATED_DB)
    shutil.copy2(PROD_DB, ISOLATED_DB)
    iconn = sqlite3.connect(ISOLATED_DB, isolation_level=None)
    iconn.row_factory = sqlite3.Row
    
    iso_pre_snap = {t: snapshot_table(iconn, t) for t in TABLES}
    ingest(iconn, results, TABLES)
    iso_post_snap = {t: snapshot_table(iconn, t) for t in TABLES}
    
    idemp_diffs = {}
    idemp_ok = True
    for t in TABLES:
        a, d, m = logical_diff(iso_pre_snap[t], iso_post_snap[t])
        idemp_diffs[t] = {'added': a, 'deleted': d, 'modified': m}
        if a > 0 or d > 0 or m > 0:
            idemp_ok = False
            
    iconn.close()
    
    # Save report data
    report_data = {
        'pre_cksum': EXPECTED_CHECKSUM,
        'backup_cksum': sha1(BACKUP_DB),
        'post_cksum': post_cksum,
        'post_integ': post_integ,
        'pre_counts': pre_counts,
        'post_counts': post_counts,
        'diffs': diffs,
        'idemp_diffs': idemp_diffs,
        'idemp_ok': idemp_ok,
        'stats': stats
    }
    
    with open(RESULTS_JSON, 'w') as f:
        json.dump(report_data, f, indent=2)
        
    print("Done. Saved results to", RESULTS_JSON)

if __name__ == "__main__":
    main()
