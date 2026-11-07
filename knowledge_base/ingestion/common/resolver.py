import sqlite3

from knowledge_base.ingestion.common.identity import (
    HELD_VARIANT_IDS, apply_dual_tone, attributes_of, compatible, identity_of, kb_gear, narrow, same_identity,
)

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
    s1, s2 = s1.lower(), s2.lower()
    if s1 == s2: return 1.0
    
    s1 = s1.replace('+', ' plus ').replace('(o)', ' optional ')
    s2 = s2.replace('+', ' plus ').replace('(o)', ' optional ')
    # Exact token inclusion
    tokens1 = set(s1.split())
    tokens2 = set(s2.split())
    
    config_words = {'petrol', 'diesel', 'cng', 'ev', 'electric', 'hybrid', 
                    'mt', 'at', 'amt', 'cvt', 'dct', 'ags', 'ivt', 'manual', 'automatic'}
    
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
        # TIE BREAKER: Penalize extra mismatched identity words
        unmatched_id = len(id1.symmetric_difference(id2))
        return 0.8 - (unmatched_id * 0.06)
        
    str1 = ' '.join(sorted(list(tokens1)))
    str2 = ' '.join(sorted(list(tokens2)))
    return SequenceMatcher(None, str1, str2).ratio()

AUTO_TRANSMISSIONS = {'automatic', 'at', 'amt', 'cvt', 'dct', 'dsg', 'dca', 'tc', 'ivt', 'torque converter', 'e-cvt'}
# Source fuel -> canonical powertrain.fuel_type values it is compatible with (beyond an exact match).
FUEL_FAMILIES = {'cng': {'cng'}, 'hybrid': {'petrol hybrid'}, 'diesel': {'diesel mild hybrid'}}

def validate_structured(c, fuel, trans, cc, price):
    warnings = []
    if fuel and c['fuel_type']:
        f1, f2 = fuel.lower(), c['fuel_type'].lower()
        if f1 != f2 and f2 not in FUEL_FAMILIES.get(f1, ()):
            warnings.append('fuel_mismatch')
    if trans and c['transmission']:
        t1 = 'auto' if trans.lower() in AUTO_TRANSMISSIONS else 'manual'
        t2 = 'auto' if c['transmission'].lower() in AUTO_TRANSMISSIONS else 'manual'
        if t1 != t2:
            warnings.append('transmission_mismatch')
    if cc and c['engine_cc'] and abs(cc - c['engine_cc']) > 50:
        warnings.append('engine_cc_mismatch')
    if price and c['price_ex_showroom'] and abs(price - c['price_ex_showroom']) > 300000:
        warnings.append('price_mismatch')
    return warnings

import re
def normalize_engine_string(engine_str):
    if not engine_str: return ""
    s = engine_str.lower()
    s = re.sub(r'(\d\.\d)\s*l(?!\w)', r'\1', s)
    s = s.replace('petrol', '').replace('diesel', '').replace('cng', '')
    s = s.replace('bi-fuel', '').replace('with hy-', '')
    return re.sub(r'\s+', ' ', s).strip()

class Resolution(tuple):
    """(variant_id, status, base_variant_id), plus .match_type, .reasons and .suggested_variant_id.

    match_type: 'identity_exact' | 'fuzzy' | 'alias' | 'ambiguous' | 'held_edition' | 'edition_candidate' | 'none'.
    Only an 'identity_exact' result carries a variant_id and may write evidence. Everything else goes to review."""
    def __new__(cls, variant_id, status, base_variant_id=None, match_type='none', reasons=(), suggested_variant_id=None):
        r = super().__new__(cls, (variant_id, status, base_variant_id))
        r.match_type, r.reasons, r.suggested_variant_id = match_type, tuple(reasons), suggested_variant_id
        return r


def _fuzzy_suggestion(all_variants, variant_name, variant_slug, edition, norm_engine, fuel, trans, cc, price):
    """The old best-match search. Scoring and thresholds are unchanged; the result only ranks a candidate for a reviewer."""
    candidates = []
    for c in all_variants:
        if validate_structured(c, fuel, trans, cc, price): continue
        test_name = variant_name
        if edition and edition.lower() not in test_name.lower():
            test_name = f"{test_name} {edition}".strip()
        test_name_with_engine = f"{test_name} {norm_engine}".strip() if norm_engine else test_name
        test_slug = (variant_slug or '').replace('-', ' ')
        if edition and edition.lower() not in test_slug.lower():
            test_slug = f"{test_slug} {edition}".strip()
        score = max(compute_similarity(test_name, c['name']), compute_similarity(test_name_with_engine, c['name']),
                    compute_similarity(test_slug, c['name']))
        source_has_edition = bool(edition) or any(kw in test_name.lower() or kw in (variant_slug or '').lower() for kw in EDITION_STRIP_HEURISTICS)
        is_canonical_edition = any(kw in c['name'].lower() for kw in EDITION_STRIP_HEURISTICS)
        if source_has_edition != is_canonical_edition:
            score = 0.0
        if score > 0:
            candidates.append((score, c))
    if not candidates: return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best = candidates[0]
    if best_score <= 0.5: return None
    if len(candidates) > 1 and (best_score - candidates[1][0]) < 0.05: return None
    return best['id']


def resolve_variant(conn, make_slug, model_slug, variant_name, variant_slug, fuel, trans, cc, price, generation_id=None, active_only=False, source_name=None, engine_name=None, edition=None):
    """Auto-accept only a unique identity match (the 10C-2 policy, for every source). See Resolution."""
    cur = conn.cursor()
    cur.execute('''
        SELECT m.id, m.name
        FROM model m
        JOIN manufacturer mfr ON m.manufacturer_id = mfr.id
        WHERE lower(replace(mfr.name, ' ', '-')) = ? AND lower(replace(m.name, ' ', '-')) = ?
    ''', (make_slug.lower(), model_slug.lower()))
    m_row = cur.fetchone()
    if not m_row: return Resolution(None, 'unresolved')
    model_id, model_name = m_row['id'], m_row['name']

    query = '''
        SELECT v.*, pt.fuel_type, pt.engine_cc, pt.power_bhp
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

    test_name = variant_name or ''
    if edition and edition.lower() not in test_name.lower():
        test_name = f"{test_name} {edition}".strip()
    attrs = attributes_of(test_name, variant_slug, fuel, trans, cc, engine_name)
    src = identity_of(test_name, model_name)
    usable = [c for c in all_variants if not validate_structured(c, fuel, trans, cc, price) and compatible(c, attrs)]

    def auto_stated(c):
        return attrs.gear == 'auto' or kb_gear(c['transmission']) == 'auto'

    matches = [c for c in usable if same_identity(identity_of(c['name'], model_name), src, model_name, auto_stated(c))]
    matches = apply_dual_tone(narrow(matches, attrs), attrs) if matches else []

    suggestion = None
    if len(matches) != 1:
        suggestion = _fuzzy_suggestion(all_variants, variant_name or '', variant_slug, edition,
                                       normalize_engine_string(engine_name) if engine_name else "", fuel, trans, cc, price)
    if len(matches) == 1:
        c = matches[0]
        if c['id'] in HELD_VARIANT_IDS:
            return Resolution(None, 'needs_review', None, 'held_edition', [f"held edition {c['id']}"], c['id'])
        return Resolution(c['id'], 'resolved', None, 'identity_exact')
    if len(matches) > 1:
        ids = [c['id'] for c in matches]
        return Resolution(None, 'needs_review', None, 'ambiguous', [f"candidates {ids}"], suggestion)

    # The source names an edition the KB doesn't have: a candidate for review, attached to its base. Never auto-created.
    if src.editions:
        plain = src._replace(editions=frozenset())
        bases = [c for c in usable if not identity_of(c['name'], model_name).editions
                 and same_identity(identity_of(c['name'], model_name), plain, model_name, auto_stated(c))]
        bases = narrow(bases, attrs)
        non_dt = apply_dual_tone(bases, attrs._replace(dual_tone=False))
        if len(non_dt) == 1:
            return Resolution(None, 'edition_candidate', non_dt[0]['id'], 'edition_candidate', [f"editions {sorted(src.editions)}"])

    # An alias or a fuzzy hit is only a hint for the reviewer.
    alias_source = source_name or '91wheels'
    cur.execute('''
        SELECT va.variant_id, va.is_verified
        FROM variant_alias va
        JOIN source s ON va.source_id = s.id
        WHERE s.name = ? AND va.alias_name = ?
    ''', (alias_source, variant_slug))
    row = cur.fetchone()
    if row:
        cand = next((c for c in all_variants if c['id'] == row['variant_id']), None)
        if cand and not validate_structured(cand, fuel, trans, cc, price):
            return Resolution(None, 'needs_review', None, 'alias', ['alias hit without identity'], row['variant_id'])
    if suggestion:
        return Resolution(None, 'needs_review', None, 'fuzzy', ['fuzzy hit without identity'], suggestion)
    return Resolution(None, 'unresolved')
