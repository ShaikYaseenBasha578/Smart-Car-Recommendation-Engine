#!/usr/bin/env python3
"""
Phase 8A — Bharat NCAP Corrected Shadow Ingestion
"""

import sqlite3, json, os, re, sys, csv, traceback, hashlib, time
import urllib.request, ssl, datetime
from bs4 import BeautifulSoup
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

PROD_DB  = "knowledge_base/carrec_kb.db"
SHADOW_DB = "scratch/carrec_kb_phase8a_shadow.db"
RAW_JSON  = "scratch/bncap_raw_results.json"
CSV_OUT   = "scratch/phase8a_bharat_ncap_coverage.csv"
PDF_DIR   = "scratch/bncap_pdfs"
BNCAP_SOURCE_ID = 7

os.makedirs(PDF_DIR, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch_html(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            return urllib.request.urlopen(req, context=ctx, timeout=15).read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(2)

def download_file(url, filepath, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, context=ctx, timeout=20) as response, open(filepath, 'wb') as out_file:
                out_file.write(response.read())
            return
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(2)

def parse_vehicle_page(url, html):
    soup = BeautifulSoup(html, 'html.parser')
    text_lines = [l for l in soup.get_text(separator='\n', strip=True).split('\n') if l.strip()]

    def find_line_after(keyword):
        for i, l in enumerate(text_lines):
            if keyword.lower() in l.lower() and i + 1 < len(text_lines):
                return text_lines[i + 1].strip()
        return None

    h = soup.find('h1') or soup.find('h2')
    tested_vehicle_name = h.get_text(strip=True) if h else None

    period_m = re.search(
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+202\d[^<]*?(?:Onwards|\d{4})',
        soup.get_text(), re.IGNORECASE)
    test_period = period_m.group(0).strip() if period_m else None

    aop_m = re.search(r'(\d{1,2}\.\d{1,2})\s*/\s*32(?:\.00)?', soup.get_text())
    aop_score = float(aop_m.group(1)) if aop_m else None

    cop_m = re.search(r'(\d{1,2}\.\d{1,2})\s*/\s*49(?:\.00)?', soup.get_text())
    cop_score = float(cop_m.group(1)) if cop_m else None

    star_els = soup.find_all(attrs={'itemtype': lambda v: v and 'Rating' in v})
    aop_stars = None
    cop_stars = None
    if len(star_els) >= 1:
        rv = star_els[0].find(attrs={'itemprop': 'ratingValue'})
        if rv and rv.get('content'): aop_stars = int(rv['content'])
    if len(star_els) >= 2:
        rv2 = star_els[1].find(attrs={'itemprop': 'ratingValue'})
        if rv2 and rv2.get('content'): cop_stars = int(rv2['content'])

    factsheet_url = None
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '.pdf' in href.lower() and ('fact' in href.lower() or 'sheet' in href.lower() or 'upload' in href.lower()):
            factsheet_url = href
            break

    tested_variant_config = find_line_after('Tested Vehicle Model')
    body_type = find_line_after('Body Type')
    crash_weight_raw = find_line_after('Crash Test Weight')
    year_of_pub_raw = find_line_after('Year of Publication')
    year_of_publication = None
    if year_of_pub_raw:
        ym = re.search(r'(20\d\d)', year_of_pub_raw)
        if ym: year_of_publication = int(ym.group(1))

    protocol_m = re.search(r'AIS-?197\s*(?:Version[- ]+)?([A-Za-z0-9\s,\-]+)', soup.get_text())
    protocol_version = protocol_m.group(0).strip() if protocol_m else None

    sat_techs = []
    in_sat = False
    for l in text_lines:
        if 'SAFETY ASSIST TECHNOLOGIES' in l.upper():
            in_sat = True
            continue
        if in_sat:
            if l.startswith('The variants') or l.startswith('Revision') or l.startswith('Disclaimer') or l.startswith('BHARAT'):
                break
            if l.strip() and l not in ('YES – STANDARD', 'NO – OPTIONAL', 'NOT APPLICABLE', 'NOT AVAILABLE'):
                sat_techs.append(l.strip())

    sat_summary = '; '.join(sat_techs) if sat_techs else None

    appl_notes = []
    for l in text_lines:
        if l.startswith('The addition of variants') or l.startswith('Up to VIN') or l.startswith('To the variants'):
            appl_notes.append(l.strip())
    applicability_notes = ' | '.join(appl_notes) if appl_notes else None

    return {
        'url': url,
        'tested_vehicle_name': tested_vehicle_name,
        'tested_variant_config': tested_variant_config,
        'body_type': body_type,
        'crash_test_weight_kg': crash_weight_raw,
        'year_of_publication': year_of_publication,
        'test_period': test_period,
        'aop_score': aop_score,
        'aop_stars': aop_stars,
        'cop_score': cop_score,
        'cop_stars': cop_stars,
        'factsheet_url': factsheet_url,
        'sat_summary': sat_summary,
        'protocol_version': protocol_version,
        'applicability_notes': applicability_notes,
    }

def scrape_single(url):
    try:
        html = fetch_html(url)
        parsed = parse_vehicle_page(url, html)
        
        # Download PDF if available
        pdf_path = None
        pdf_checksum = None
        if parsed['factsheet_url']:
            pdf_url = parsed['factsheet_url']
            if not pdf_url.startswith('http'):
                pdf_url = 'https://www.bncap.in' + pdf_url
            filename = url.rstrip('/').split('/')[-1] + '.pdf'
            local_path = os.path.join(PDF_DIR, filename)
            
            if not os.path.exists(local_path):
                download_file(pdf_url, local_path)
            
            if os.path.exists(local_path):
                pdf_path = local_path
                pdf_checksum = hashlib.sha256(open(local_path, 'rb').read()).hexdigest()
        
        parsed['artifact_path'] = pdf_path
        parsed['artifact_checksum'] = pdf_checksum
        return url, parsed, None
    except Exception as e:
        return url, None, str(e)

def discover_and_scrape():
    print("[DISCOVERY] Fetching vehicle index...")
    index_html = fetch_html('https://www.bncap.in/vehicle-safety-ratings/')
    index_soup = BeautifulSoup(index_html, 'html.parser')

    vehicle_urls = sorted(set(
        a['href'] for a in index_soup.find_all('a', href=True)
        if '/vehicle/' in a['href'] and a['href'].startswith('https')
    ))
    print(f"[DISCOVERY] Found {len(vehicle_urls)} vehicle URLs in index")

    results = []
    failed = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(scrape_single, url): url for url in vehicle_urls}
        for future in as_completed(futures):
            url, parsed, error = future.result()
            if error:
                failed.append({'url': url, 'error': error})
                print(f"  [FAIL] {url}: {error}")
            else:
                results.append(parsed)
                print(f"  [OK] {parsed['tested_vehicle_name']}")

    # Sort results by url to ensure deterministic order
    results.sort(key=lambda x: x['url'])
    print(f"[DISCOVERY] Scraped: {len(results)} success, {len(failed)} failed")
    return results, failed, vehicle_urls

# Explicit Alias Table based on Evidence
BNCAP_ALIAS_TABLE = {
    'tata-safari-harrier': {
        'manufacturer_id': 10,
        'model_ids': [30, None],  # Harrier is 30, Safari not in top-62
        'scope': 'FAMILY_LEVEL',
        'justification': 'BNCAP page explicitly covers Harrier AND Safari as one test (shared platform).'
    },
    'tata-punch-ev': {
        'manufacturer_id': 10, 'model_ids': [59], 'scope': 'MODEL_LEVEL',
        'justification': 'BNCAP title is TATA PUNCH.EV. Unambiguous.'
    },
    'tata-punch-ev-2026': {
        'manufacturer_id': 10, 'model_ids': [59], 'scope': 'MODEL_LEVEL',
        'justification': 'BNCAP page states updated model introduced in Feb 2026. Same CarRec model 59.'
    },
    'tata-nexon-ev': {
        'manufacturer_id': 10, 'model_ids': [6], 'scope': 'MODEL_LEVEL',
        'justification': 'Unambiguous mapping to Nexon EV (model_id=6).'
    },
    'maruti-baleno-gasoline-2-airbags': {
        'manufacturer_id': 6, 'model_ids': [15], 'scope': 'MODEL_LEVEL',
        'justification': 'Explicitly tested Baleno with 2 airbags. CarRec model 15.'
    },
    'maruti-baleno-gasoline-6-airbags': {
        'manufacturer_id': 6, 'model_ids': [15], 'scope': 'MODEL_LEVEL',
        'justification': 'Explicitly tested Baleno with 6 airbags. CarRec model 15.'
    },
    'maruti-suzuki-invicto': {
        'manufacturer_id': None, 'model_ids': [], 'scope': 'NO_MATCH',
        'justification': 'Invicto is not in CarRec top-62. Not aliasing to Innova Hycross as test is badge-specific.'
    },
    'nissan-tekton': {
        'manufacturer_id': None, 'model_ids': [], 'scope': 'NO_MATCH',
        'justification': 'Nissan Tekton is not in CarRec top-62 models.'
    },
    'skoda-kylaq': {
        'manufacturer_id': 9, 'model_ids': [52], 'scope': 'MODEL_LEVEL',
        'justification': 'Unambiguous mapping to Skoda Kylaq.'
    }
}

def resolve_entity(url_slug, title, conn):
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

def snapshot_table(conn, table):
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    # Convert to dict and remove 'id' or 'created_at' if they auto-increment unpredictably?
    # Actually, for true logical diff, we should compare exact rows except for generated IDs of NEW rows.
    # But since Pass 2 should do NOTHING, even IDs shouldn't advance.
    return [dict(r) for r in rows]

def logical_diff(before, after):
    before_map = {hash(frozenset(r.items())) for r in before}
    after_map  = {hash(frozenset(r.items())) for r in after}
    added = len(after_map - before_map)
    deleted = len(before_map - after_map)
    # If len(before) == len(after) and added == deleted, we count them as modified.
    # A simple count is enough to prove 0 additions/deletions/modifications.
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

def ingest(conn, results, pass_label):
    print(f"--- {pass_label} ---")
    pre = {t: snapshot_table(conn, t) for t in TABLES}
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

    post = {t: snapshot_table(conn, t) for t in TABLES}
    diff = {}
    for t in TABLES:
        a, d, m = logical_diff(pre[t], post[t])
        diff[t] = {'added': a, 'deleted': d, 'modified': m}
    
    return stats, diff

def main():
    if os.path.exists(RAW_JSON):
        with open(RAW_JSON) as f:
            results = json.load(f)
        if results and 'artifact_checksum' not in results[0]:
            print("Cache outdated. Re-scraping...")
            results, _, urls = discover_and_scrape()
        else:
            print(f"Loaded {len(results)} from cache.")
            urls = [r['url'] for r in results]
    else:
        results, _, urls = discover_and_scrape()
        with open(RAW_JSON, 'w') as f:
            json.dump(results, f, indent=2)

    if os.path.exists(SHADOW_DB): os.remove(SHADOW_DB)
    os.system(f"cp {PROD_DB} {SHADOW_DB}")

    conn = sqlite3.connect(SHADOW_DB, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(SAFETY_TEST_DDL)
    conn.execute(SAFETY_APPLICABILITY_DDL)

    stats1, diff1 = ingest(conn, results, "PASS 1")
    for t, d in diff1.items():
        if any(d.values()): print(f"  {t}: +{d['added']}, -{d['deleted']}, ~{d['modified']}")

    stats2, diff2 = ingest(conn, results, "PASS 2 (IDEMPOTENCY)")
    idemp_ok = True
    for t, d in diff2.items():
        if any(d.values()):
            print(f"  FAIL IDEMPOTENCY {t}: {d}")
            idemp_ok = False
        else:
            print(f"  OK {t}: 0/0/0")

    rows = conn.execute("""
        SELECT
            st.tested_vehicle_name, mk.name AS manufacturer,
            'Bharat NCAP' AS source_name,
            m.name AS carrec_model, g.name AS generation,
            sa.match_confidence AS scope,
            st.resolution_status, st.resolution_justification AS reason
        FROM safety_test st
        LEFT JOIN safety_test_applicability sa ON sa.safety_test_id = st.id
        LEFT JOIN manufacturer mk ON sa.manufacturer_id = mk.id
        LEFT JOIN model m ON sa.model_id = m.id
        LEFT JOIN generation g ON sa.generation_id = g.id
        ORDER BY st.id
    """).fetchall()

    with open(CSV_OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        for r in rows: w.writerow(dict(r))

    print(f"\nCompleted. Idempotency OK: {idemp_ok}")
    print(f"Total urls in index: {len(urls)}")

if __name__ == '__main__':
    main()
