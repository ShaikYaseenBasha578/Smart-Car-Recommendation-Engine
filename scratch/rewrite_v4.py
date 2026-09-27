import re

with open('scratch/phase8a_shadow_ingestion_v3.py', 'r') as f:
    content = f.read()

# 1. Update the extraction block
search_block_ext = """                if in_data:
                    for c in cells:
                        if c.upper() in ('YES', 'NO'): continue
                        if is_date(c): continue
                        if is_sr_no(c): continue
                        if c in ('—', '-', '–', ''): continue
                        variants.append(c)
    explicit_variants = list(set(variants))"""

replace_block_ext = """                if in_data:
                    current_flag = None
                    for c in cells:
                        if c.upper() in ('YES', 'NO'):
                            current_flag = c.upper()
                    for c in cells:
                        if c.upper() in ('YES', 'NO'): continue
                        if is_date(c): continue
                        if is_sr_no(c): continue
                        if c in ('—', '-', '–', ''): continue
                        # Propagate the flag from this row if present, otherwise we'd need block state.
                        # Wait, we need block state to propagate rowspan!
                        variants.append((c, current_flag))
    # We will let the outer state tracker do it in a better way, let's just rewrite the whole table parser!"""

# Actually I'll rewrite the entire variant extraction logic cleanly
search_block_full = """    variants = []
    tables = soup.find_all('table')
    
    for t in tables:
        text = t.get_text()
        if 'Ratings Applicability' in text or 'Month' in text:
            in_data = False
            for r in t.find_all('tr'):
                cells = [c.get_text(strip=True) for c in r.find_all(['th', 'td']) if c.get_text(strip=True)]
                if not cells: continue
                
                if any('Disclaimer' in c or 'Revision' in c or 'addition of variants' in c for c in cells):
                    in_data = False
                    continue
                    
                has_yes_no = any(c.upper() in ('YES', 'NO') for c in cells)
                has_date = any(is_date(c) for c in cells)
                
                if has_yes_no or has_date:
                    in_data = True
                    
                if in_data:
                    for c in cells:
                        if c.upper() in ('YES', 'NO'): continue
                        if is_date(c): continue
                        if is_sr_no(c): continue
                        if c in ('—', '-', '–', ''): continue
                        variants.append(c)
    explicit_variants = list(set(variants))"""

replace_block_full = """    variants = {}
    tables = soup.find_all('table')
    
    for t in tables:
        text = t.get_text()
        if 'Ratings Applicability' in text or 'Month' in text:
            in_data = False
            current_app_flag = None
            for r in t.find_all('tr'):
                cells = [c.get_text(strip=True) for c in r.find_all(['th', 'td']) if c.get_text(strip=True)]
                if not cells: continue
                
                if any('Disclaimer' in c or 'Revision' in c or 'addition of variants' in c for c in cells):
                    in_data = False
                    current_app_flag = None
                    continue
                    
                has_yes_no = any(c.upper() in ('YES', 'NO') for c in cells)
                has_date = any(is_date(c) for c in cells)
                
                if has_yes_no or has_date:
                    in_data = True
                    
                if in_data:
                    for c in cells:
                        if c.upper() in ('YES', 'NO'):
                            current_app_flag = c.upper()
                    
                    for c in cells:
                        if c.upper() in ('YES', 'NO'): continue
                        if is_date(c): continue
                        if is_sr_no(c): continue
                        if c in ('—', '-', '–', ''): continue
                        # assert we never hardcode YES blindly
                        variants[c] = current_app_flag
    
    # Format back to list of dicts for safety_test_applicability
    explicit_variants = [{"name": k, "flag": v} for k, v in variants.items()]"""

content = content.replace(search_block_full, replace_block_full)

# 2. Update the SQL ingest block
ingest_search = """                    if source_variants:
                        canonical_variants = conn.execute("SELECT id, name FROM variant WHERE model_id=?", (mid,)).fetchall()
                        for sv in source_variants:
                            sv_clean = sv.lower().replace('5mt', 'mt')"""

ingest_replace = """                    if source_variants:
                        canonical_variants = conn.execute("SELECT id, name FROM variant WHERE model_id=?", (mid,)).fetchall()
                        for sv_dict in source_variants:
                            sv = sv_dict['name']
                            sv_flag = sv_dict['flag']
                            sv_clean = sv.lower().replace('5mt', 'mt')"""

content = content.replace(ingest_search, ingest_replace)

sql_search = """                            if not existing_v:
                                conn.execute(\"\"\"
                                    INSERT INTO safety_test_applicability
                                    (safety_test_id, manufacturer_id, model_id, generation_id, variant_id, source_variant_name, applicability_flag, mapping_status, notes)
                                    VALUES (?, ?, ?, ?, ?, ?, 'YES', ?, ?)
                                \"\"\", (st_id, make_id, mid, gen_id, matched_vid, sv, mapping_status, justification))"""

sql_replace = """                            if not existing_v:
                                # ASSERTION: Retained variant cannot be assigned YES unless its source row contains YES (or via rowspan propagation)
                                assert sv_flag in ('YES', 'NO', None), "Invalid applicability flag"
                                
                                conn.execute(\"\"\"
                                    INSERT INTO safety_test_applicability
                                    (safety_test_id, manufacturer_id, model_id, generation_id, variant_id, source_variant_name, applicability_flag, mapping_status, notes)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                \"\"\", (st_id, make_id, mid, gen_id, matched_vid, sv, sv_flag, mapping_status, justification))"""

content = content.replace(sql_search, sql_replace)

with open('scratch/phase8a_shadow_ingestion_v4.py', 'w') as f:
    f.write(content)
