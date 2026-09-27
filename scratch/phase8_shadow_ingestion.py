import sqlite3, json, os, re, sys
from collections import defaultdict

DB = "scratch/carrec_kb_phase8_shadow.db"

# Create a pristine copy
if os.path.exists(DB):
    os.remove(DB)
os.system(f"cp knowledge_base/carrec_kb.db {DB}")

def run_pass(conn, pass_num):
    print(f"\n--- PASS {pass_num} ---")
    
    c = conn.execute("SELECT count(*) FROM safety_test")
    pre_tests = c.fetchone()[0]
    c = conn.execute("SELECT count(*) FROM safety_test_applicability")
    pre_appls = c.fetchone()[0]
    
    with open('scratch/bncap_raw_results.json', 'r') as f:
        raw_results = json.load(f)

    def resolve_entity(title):
        t_clean = title.lower().replace("-", " ").replace(".", " ").strip()
        c = conn.execute("SELECT m.id as model_id, m.name as model, mk.id as make_id, mk.name as make FROM model m JOIN manufacturer mk ON m.manufacturer_id=mk.id")
        for row in c.fetchall():
            db_make = row['make'].lower().replace(" ", "")
            db_model = row['model'].lower().replace("-", "").replace(" ", "")
            t_nospace = t_clean.replace(" ", "")
            if db_make in t_nospace and db_model in t_nospace:
                return row['make_id'], row['model_id'], row['make'], row['model']
                
        # Aliases
        if 'safari' in t_clean or 'harrier' in t_clean: return 12, 53, 'Tata', 'Harrier'
        if 'punch' in t_clean and 'ev' in t_clean: return 12, 56, 'Tata', 'Punch EV'
        if 'punch' in t_clean and 'ev' not in t_clean: return 12, 55, 'Tata', 'Punch'
        if 'xuv 3xo' in t_clean or '3xo' in t_clean: return 5, 23, 'Mahindra', 'XUV 3XO'
        if 'xuv 7xo' in t_clean or '7xo' in t_clean: return 5, 24, 'Mahindra', 'XUV 7XO'
        if 'dzire' in t_clean: return 7, 33, 'Maruti Suzuki', 'Dzire'
        if 'baleno' in t_clean: return 7, 31, 'Maruti Suzuki', 'Baleno'
        if 'brezza' in t_clean: return 7, 32, 'Maruti Suzuki', 'Brezza'
        if 'victoris' in t_clean: return 7, 40, 'Maruti Suzuki', 'Victoris'
        if 'kylaq' in t_clean: return 11, 48, 'Skoda', 'Kylaq'
        if 'tucson' in t_clean: return 3, 13, 'Hyundai', 'Tucson'
        
        return None, None, None, None

    stats = defaultdict(int)

    try:
        conn.execute("BEGIN TRANSACTION")
        source_id = 7
        
        for res in raw_results:
            url = res['url']
            title = res.get('title', '')
            aop = res.get('aop_score')
            cop = res.get('cop_score')
            pdf = res.get('pdf_url')
            period = res.get('period')
            
            make_id, model_id, make_name, model_name = resolve_entity(title)
            
            status = 'NO_MATCH'
            if model_id:
                status = 'RESOLVED'
            elif 'curvv' in title.lower() or 'basalt' in title.lower() or 'sierra' in title.lower() or 'tekton' in title.lower() or 'xev' in title.lower() or 'invicto' in title.lower() or 'vf' in title.lower():
                status = 'NO_MATCH' 
            else:
                status = 'UNRESOLVED'
                
            conn.execute("""
                INSERT OR IGNORE INTO safety_test 
                (source_id, tested_vehicle_name, test_period, aop_score, cop_score, factsheet_url, raw_source_url, resolution_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (source_id, title, period, aop, cop, pdf, url, status))
            
            c = conn.execute("SELECT id FROM safety_test WHERE raw_source_url=?", (url,))
            test_id = c.fetchone()['id']
            
            stats[status] += 1
            
            if status == 'RESOLVED':
                c = conn.execute("SELECT id FROM variant WHERE model_id=?", (model_id,))
                variants = c.fetchall()
                for v in variants:
                    conn.execute("""
                        INSERT OR IGNORE INTO safety_test_applicability
                        (safety_test_id, manufacturer_id, model_id, variant_id, match_confidence)
                        VALUES (?, ?, ?, ?, ?)
                    """, (test_id, make_id, model_id, v['id'], 'MODEL_LEVEL'))
                    
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        print("Ingestion error:", e)

    c = conn.execute("SELECT count(*) FROM safety_test")
    post_tests = c.fetchone()[0]
    c = conn.execute("SELECT count(*) FROM safety_test_applicability")
    post_appls = c.fetchone()[0]
    
    print(f"Status counts: {dict(stats)}")
    print(f"safety_test: +{post_tests - pre_tests} rows")
    print(f"safety_test_applicability: +{post_appls - pre_appls} rows")
    
    if pass_num == 1:
        import csv
        rows = conn.execute("""
            SELECT 
                st.tested_vehicle_name as tested_vehicle,
                st.test_period as test_date,
                st.aop_score,
                st.cop_score,
                st.resolution_status,
                'https://www.bncap.in' as source,
                st.factsheet_url as source_document,
                mk.name as manufacturer,
                m.name as model,
                sa.match_confidence as applicability_scope,
                count(v.id) as variants_mapped
            FROM safety_test st
            LEFT JOIN safety_test_applicability sa ON sa.safety_test_id = st.id
            LEFT JOIN manufacturer mk ON sa.manufacturer_id = mk.id
            LEFT JOIN model m ON sa.model_id = m.id
            LEFT JOIN variant v ON sa.variant_id = v.id
            GROUP BY st.id
        """).fetchall()
        
        with open('scratch/phase8_bharat_ncap_coverage.csv', 'w', newline='') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                for r in rows:
                    writer.writerow(dict(r))
        print("Wrote scratch/phase8_bharat_ncap_coverage.csv")

conn = sqlite3.connect(DB, isolation_level=None)
conn.row_factory = sqlite3.Row
conn.execute("""
CREATE TABLE IF NOT EXISTS safety_test (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES source(id),
    tested_vehicle_name TEXT,
    test_period TEXT,
    aop_score REAL,
    cop_score REAL,
    stars INTEGER,
    factsheet_url TEXT,
    raw_source_url TEXT UNIQUE,
    resolution_status TEXT,
    created_at TEXT DEFAULT (datetime('now'))
)
""")
conn.execute("""
CREATE TABLE IF NOT EXISTS safety_test_applicability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    safety_test_id INTEGER REFERENCES safety_test(id),
    manufacturer_id INTEGER REFERENCES manufacturer(id),
    model_id INTEGER REFERENCES model(id),
    generation_id INTEGER REFERENCES generation(id),
    variant_id INTEGER REFERENCES variant(id),
    match_confidence TEXT,
    notes TEXT,
    UNIQUE(safety_test_id, variant_id)
)
""")

run_pass(conn, 1)
run_pass(conn, 2)

conn.close()
