import sqlite3

EDITION_STRIP_HEURISTICS = [
    "dark edition", "knight edition", "special edition", 
    "black edition", "anniversary edition", "summer edition",
    "dual tone", "kaziranga edition", "jet edition", "camo edition",
    "red dark edition", "matte edition"
]

from difflib import SequenceMatcher



def compute_similarity(s1, s2):
    if not s1 or not s2: return 0.0
    from difflib import SequenceMatcher
    import re
    
    def get_tokens(s):
        s = s.replace('-', ' ').lower()
        s = s.replace('manual', 'mt').replace('automatic', 'at')
        s = re.sub(r'\b\d\.\d+l\b', '', s)
        s = s.replace('turbo', '').replace('vtvt', '').replace('mpi', '').replace('crdi', '')
        s = s.replace('+', ' plus ')
        s = s.replace('(o)', ' optional ')
        return set(s.split())
        
    tokens1 = get_tokens(s1)
    tokens2 = get_tokens(s2)
    
    if not tokens1 or not tokens2: return 0.0
    if tokens1 == tokens2: return 1.0
    
    config_words = {'petrol', 'diesel', 'cng', 'ev', 'mt', 'at', 'cvt', 'dct', 'amt', 'awd', '4x4', 'fwd', 'rwd', 'hybrid', 'electric'}
    
    id1 = tokens1 - config_words
    id2 = tokens2 - config_words
    
    if id1 and id2:
        id_overlap = len(id1.intersection(id2))
        if id_overlap == 0:
            return 0.0
            
    # If identity overlaps, or one of them has NO identity tokens (e.g. just "Petrol MT"),
    # we fall back to normal similarity on the FULL tokens so config differences (CNG vs Petrol) are scored properly.
    
    overlap = len(tokens1.intersection(tokens2))
    if overlap == len(tokens1) or overlap == len(tokens2): 
        # But wait! If one is a subset, e.g. "VXi Petrol Manual" vs "VXi CNG Manual", overlap is NOT subset.
        # "VXi Petrol Manual" -> vxi, petrol, mt
        # "VXi CNG Manual" -> vxi, cng, mt
        # overlap = 2. It will fall to SequenceMatcher.
        return 0.8
        
    str1 = ' '.join(sorted(list(tokens1)))
    str2 = ' '.join(sorted(list(tokens2)))
    return SequenceMatcher(None, str1, str2).ratio()

def validate_structured(c, fuel, trans, cc, price):
    warnings = []
    if fuel and c['fuel_type']:
        f1, f2 = fuel.lower(), c['fuel_type'].lower()
        if f1 != f2:
            if not (f1 == 'cng' and 'petrol' in f2):
                warnings.append('fuel_mismatch')
    if trans and c['transmission']:
        t1 = 'auto' if trans.lower() in ['automatic', 'amt', 'cvt', 'dct', 'tc', 'ivt', 'dca', 'torque converter', 'e-cvt'] else 'manual'
        t2 = 'auto' if c['transmission'].lower() in ['automatic', 'amt', 'cvt', 'dct', 'tc', 'ivt', 'torque converter', 'e-cvt'] else 'manual'
        if t1 != t2:
            warnings.append('transmission_mismatch')
    if cc and c['engine_cc'] and abs(cc - c['engine_cc']) > 50:
        warnings.append('engine_cc_mismatch')
    if price and c['price_ex_showroom'] and abs(price - c['price_ex_showroom']) > 300000:
        warnings.append('price_mismatch')
    return warnings

def resolve_variant(conn, make_slug, model_slug, variant_name, variant_slug, fuel, trans, cc, price, generation_id=None, active_only=False, source_name=None, engine_name=None, edition=None):
    cur = conn.cursor()
    cur.execute('''
        SELECT m.id
        FROM model m
        JOIN manufacturer mfr ON m.manufacturer_id = mfr.id
        WHERE lower(replace(mfr.name, ' ', '-')) = ? AND lower(replace(m.name, ' ', '-')) = ?
    ''', (make_slug.lower(), model_slug.lower()))
    m_row = cur.fetchone()
    if not m_row: return None, 'unresolved', None
    model_id = m_row['id']
    
    query = '''
        SELECT v.id, v.name, pt.fuel_type, pt.engine_cc, pt.power_bhp, v.transmission, v.price_ex_showroom, v.base_variant_id
        FROM variant v
        JOIN powertrain pt ON v.powertrain_id = pt.id
        WHERE v.model_id = ?
    '''
    params = [model_id]
    
    if generation_id is not None:
        query += " AND v.generation_id = ?"
        params.append(generation_id)
        
    if active_only:
        query += " AND v.is_discontinued = 0"
        
    cur.execute(query, tuple(params))
    all_variants = cur.fetchall()
    
    if source_name:
        cur.execute('''
            SELECT va.variant_id, va.needs_review, va.is_verified
            FROM variant_alias va
            JOIN source s ON va.source_id = s.id
            WHERE s.name = ? AND va.alias_name = ?
        ''', (source_name, variant_slug))
    else:
        cur.execute('''
            SELECT va.variant_id, va.needs_review, va.is_verified
            FROM variant_alias va
            JOIN source s ON va.source_id = s.id
            WHERE s.name = '91wheels' AND va.alias_name = ?
        ''', (variant_slug,))
    row = cur.fetchone()
    
    if row:
        c_id = row['variant_id']
        cand = next((c for c in all_variants if c['id'] == c_id), None)
        if cand:
            warnings = validate_structured(cand, fuel, trans, cc, price)
            if warnings:
                if row['is_verified'] == 1:
                    return c_id, 'resolved_with_warning', None
                # Discard bad historical alias
            else:
                status = 'resolved' if row['is_verified'] else 'resolved_with_warning'
                if row['needs_review']: status = 'resolved_with_warning'
                return c_id, status, None
                
    # 1. Exact Match Check First (Highest Priority)
    for c in all_variants:
        warnings = validate_structured(c, fuel, trans, cc, price)
        if warnings: continue
        
        # If edition is explicitly passed, require it for an exact match
        source_has_edition = bool(edition) or any(kw in variant_name.lower() or kw in variant_slug.lower() for kw in EDITION_STRIP_HEURISTICS)
        is_canonical_edition = any(kw in c['name'].lower() for kw in EDITION_STRIP_HEURISTICS)
        if source_has_edition != is_canonical_edition:
            continue
            
        # Combine variant name with edition if we have a structured edition
        test_name = variant_name
        if edition and edition.lower() not in variant_name.lower():
            test_name = f"{variant_name} {edition}".strip()
            
        if c['name'].lower() == test_name.lower() or c['name'].lower() == variant_slug.replace('-', ' ').lower():
            return c['id'], 'resolved', None

    # 2. Fuzzy Scoring with Margin Validation
    candidates = []
    for c in all_variants:
        warnings = validate_structured(c, fuel, trans, cc, price)
        if warnings: continue
        
        test_name = variant_name
        if edition and edition.lower() not in variant_name.lower():
            test_name = f"{variant_name} {edition}".strip()
            
        test_slug = variant_slug.replace('-', ' ')
        if edition and edition.lower() not in test_slug.lower():
            test_slug = f"{test_slug} {edition}".strip()
            
        score = max(compute_similarity(test_name, c['name']), compute_similarity(test_slug, c['name']))
        
        # Block cross-edition fuzzy matching
        source_has_edition = bool(edition) or any(kw in test_name.lower() or kw in variant_slug.lower() for kw in EDITION_STRIP_HEURISTICS)
        is_canonical_edition = any(kw in c['name'].lower() for kw in EDITION_STRIP_HEURISTICS)
        if source_has_edition != is_canonical_edition:
            score = 0.0

        if score > 0:
            candidates.append((score, c))
            
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_match = candidates[0]
        
        if best_score > 0.5:
            # Enforce Minimum Margin
            if len(candidates) > 1:
                second_best_score = candidates[1][0]
                if (best_score - second_best_score) < 0.05:
                    return None, 'unresolved', None
                    
            warnings = validate_structured(best_match, fuel, trans, cc, price)
            if warnings: return best_match['id'], 'needs_review', None
            return best_match['id'], 'resolved', None

    # EDITION FALLBACK

    
    lower_name = variant_name.lower()
    has_heuristic = False
    stripped_name = variant_name
    for kw in EDITION_STRIP_HEURISTICS:
        if kw in lower_name:
            stripped_name = lower_name.replace(kw, '').strip()
            has_heuristic = True
            break
            
    print('FB1:', edition, has_heuristic); if edition or has_heuristic:
        best_sub_score = 0
        best_sub_match = None
        for c in all_variants:
            # We only want to attach to base variants, not other editions ideally
            is_c_edition = any(kw in c['name'].lower() for kw in EDITION_STRIP_HEURISTICS)
            if is_c_edition: continue
            
            warnings = validate_structured(c, fuel, trans, cc, price)
            if warnings: continue
            
            score = compute_similarity(stripped_name, c['name'])
            if score > best_sub_score:
                best_sub_score = score
                best_sub_match = c
                
        print('FB2:', best_sub_match['name'] if best_sub_match else None, best_sub_score); if best_sub_match and best_sub_score > 0.6:
            return None, 'edition_candidate', best_sub_match['id']
                
    return None, 'unresolved', None

