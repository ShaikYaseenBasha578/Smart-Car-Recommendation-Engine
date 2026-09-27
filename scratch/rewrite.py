import re

with open('scratch/phase8a_shadow_ingestion.py', 'r') as f:
    content = f.read()

# 1. Update DDL
old_ddl = """CREATE TABLE IF NOT EXISTS safety_test_applicability (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    safety_test_id    INTEGER NOT NULL REFERENCES safety_test(id),
    manufacturer_id   INTEGER REFERENCES manufacturer(id),
    model_id          INTEGER REFERENCES model(id),
    generation_id     INTEGER REFERENCES generation(id),
    variant_id        INTEGER REFERENCES variant(id),
    match_confidence  TEXT NOT NULL,
    notes             TEXT,
    UNIQUE(safety_test_id, model_id, match_confidence)
)"""

new_ddl = """CREATE TABLE IF NOT EXISTS safety_test_applicability (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    safety_test_id    INTEGER NOT NULL REFERENCES safety_test(id),
    manufacturer_id   INTEGER REFERENCES manufacturer(id),
    model_id          INTEGER REFERENCES model(id),
    generation_id     INTEGER REFERENCES generation(id),
    variant_id        INTEGER REFERENCES variant(id),
    source_variant_name TEXT,
    applicability_flag TEXT,
    mapping_status    TEXT NOT NULL,
    notes             TEXT,
    UNIQUE(safety_test_id, model_id, variant_id, source_variant_name, mapping_status)
)"""

content = content.replace(old_ddl, new_ddl)

# 2. Add extract_variants_from_soup to parse_vehicle_page
parser_search = """    appl_notes = []
    for l in text_lines:
        if l.startswith('The addition of variants') or l.startswith('Up to VIN') or l.startswith('To the variants'):
            appl_notes.append(l.strip())
    applicability_notes = ' | '.join(appl_notes) if appl_notes else None"""

parser_replace = """    appl_notes = []
    for l in text_lines:
        if l.startswith('The addition of variants') or l.startswith('Up to VIN') or l.startswith('To the variants'):
            appl_notes.append(l.strip())
    applicability_notes = ' | '.join(appl_notes) if appl_notes else None

    # Extract variants
    variants = []
    tables = soup.find_all('table')
    in_variant_section = False
    for t in tables:
        text = t.get_text()
        if 'The variants to which' in text or 'Ratings Applicability' in text and 'Month' in text:
            in_variant_section = True
            
        if in_variant_section:
            if 'Child restraint' in text or 'Dynamic score' in text:
                break
            
            for row in t.find_all('tr'):
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th']) if td.get_text(strip=True)]
                if not cells: continue
                if 'Month &' in cells[-1] or 'Revision' in cells[0] or 'Disclaimer' in cells[0] or 'The addition' in cells[0]:
                    continue
                
                filtered = [c for c in cells if c not in ('YES', 'NO') and not re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \\d{4}$', c)]
                for v in filtered:
                    if v.upper() == v and len(v) > 1 and 'FAMILY' not in v.upper():
                        variants.append(v)
    explicit_variants = list(set(variants))"""

content = content.replace(parser_search, parser_replace)

# 3. Add explicit_variants to return dict
ret_search = """        'applicability_notes': applicability_notes,
    }"""
ret_replace = """        'applicability_notes': applicability_notes,
        'explicit_variants': explicit_variants,
    }"""
content = content.replace(ret_search, ret_replace)

# 4. Update Ingest
ingest_search = """            # Insert applicability ONLY IF NOT EXISTS
            if res_status in ('RESOLVED', 'FAMILY_LEVEL') and model_ids and st_id:
                for mid in model_ids:
                    if mid is None: continue
                    existing_sa = conn.execute(
                        "SELECT id FROM safety_test_applicability WHERE safety_test_id=? AND model_id=? AND match_confidence=?",
                        (st_id, mid, scope)
                    ).fetchone()
                    if not existing_sa:
                        conn.execute(\"\"\"
                            INSERT INTO safety_test_applicability
                            (safety_test_id, manufacturer_id, model_id, generation_id, variant_id, match_confidence, notes)
                            VALUES (?, ?, ?, ?, NULL, ?, ?)
                        \"\"\", (st_id, make_id, mid, gen_id if scope == 'MODEL_LEVEL' else None, scope, justification))"""

ingest_replace = """            # Insert applicability ONLY IF NOT EXISTS
            if res_status in ('RESOLVED', 'FAMILY_LEVEL') and model_ids and st_id:
                for mid in model_ids:
                    if mid is None: continue
                    
                    source_variants = res.get('explicit_variants', [])
                    high_level_status = 'FAMILY_SCOPE' if scope == 'FAMILY_LEVEL' else 'MODEL_SCOPE'
                    
                    # 1. Insert high-level scope
                    existing_sa = conn.execute(
                        "SELECT id FROM safety_test_applicability WHERE safety_test_id=? AND model_id=? AND mapping_status=?",
                        (st_id, mid, high_level_status)
                    ).fetchone()
                    if not existing_sa:
                        conn.execute(\"\"\"
                            INSERT INTO safety_test_applicability
                            (safety_test_id, manufacturer_id, model_id, generation_id, variant_id, source_variant_name, applicability_flag, mapping_status, notes)
                            VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
                        \"\"\", (st_id, make_id, mid, gen_id if high_level_status == 'MODEL_SCOPE' else None, high_level_status, justification))
                    
                    # 2. Insert explicit variants
                    if source_variants:
                        canonical_variants = conn.execute("SELECT id, name FROM variant WHERE model_id=?", (mid,)).fetchall()
                        for sv in source_variants:
                            sv_clean = sv.lower().replace('5mt', 'mt')
                            matched_vid = None
                            matches = []
                            for cv in canonical_variants:
                                cv_words = set(re.findall(r'[a-z0-9]+', cv['name'].lower()))
                                sv_words = set(re.findall(r'[a-z0-9]+', sv_clean))
                                if cv_words.issubset(sv_words):
                                    matches.append(cv['id'])
                            
                            if len(matches) == 1:
                                mapping_status = 'EXACT_CANONICAL_VARIANT'
                                matched_vid = matches[0]
                            else:
                                mapping_status = 'EXPLICIT_SOURCE_VARIANT_UNRESOLVED'
                                
                            existing_v = conn.execute(
                                "SELECT id FROM safety_test_applicability WHERE safety_test_id=? AND model_id=? AND source_variant_name=? AND mapping_status=?",
                                (st_id, mid, sv, mapping_status)
                            ).fetchone()
                            if not existing_v:
                                conn.execute(\"\"\"
                                    INSERT INTO safety_test_applicability
                                    (safety_test_id, manufacturer_id, model_id, generation_id, variant_id, source_variant_name, applicability_flag, mapping_status, notes)
                                    VALUES (?, ?, ?, ?, ?, ?, 'YES', ?, ?)
                                \"\"\", (st_id, make_id, mid, gen_id, matched_vid, sv, mapping_status, justification))"""

content = content.replace(ingest_search, ingest_replace)

with open('scratch/phase8a_shadow_ingestion_v2.py', 'w') as f:
    f.write(content)

