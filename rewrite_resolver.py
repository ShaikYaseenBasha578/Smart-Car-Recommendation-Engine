with open("knowledge_base/ingestion/common/resolver.py", "r") as f:
    code = f.read()

import re

# Update resolve_variant signature
code = code.replace(
    "def resolve_variant(conn, make_slug, model_slug, variant_name, variant_slug, fuel, trans, cc, price, generation_id=None, active_only=False):",
    "def resolve_variant(conn, make_slug, model_slug, variant_name, variant_slug, fuel, trans, cc, price, generation_id=None, active_only=False, source_name=None):"
)

# Replace alias query
old_alias = '''    cur.execute(\'''
        SELECT va.variant_id, va.needs_review, va.is_verified
        FROM variant_alias va
        JOIN source s ON va.source_id = s.id
        WHERE s.name = '91wheels' AND va.alias_name = ?
    \''', (variant_slug,))'''

new_alias = '''    if source_name:
        cur.execute(\'''
            SELECT va.variant_id, va.needs_review, va.is_verified
            FROM variant_alias va
            JOIN source s ON va.source_id = s.id
            WHERE s.name = ? AND va.alias_name = ?
        \''', (source_name, variant_slug))
    else:
        cur.execute(\'''
            SELECT va.variant_id, va.needs_review, va.is_verified
            FROM variant_alias va
            JOIN source s ON va.source_id = s.id
            WHERE s.name = '91wheels' AND va.alias_name = ?
        \''', (variant_slug,))'''

code = code.replace(old_alias, new_alias)

# Extract everything between alias row handler and EDITION FALLBACK
start_idx = code.find("    best_matches = []")
end_idx = code.find("    # EDITION FALLBACK")

new_fuzzy_logic = '''    # 1. Exact Match Check First (Highest Priority)
    for c in all_variants:
        warnings = validate_structured(c, fuel, trans, cc, price)
        if warnings: continue
        if c['name'].lower() == variant_name.lower() or c['name'].lower() == variant_slug.replace('-', ' ').lower():
            return c['id'], 'resolved', None

    # 2. Fuzzy Scoring with Margin Validation
    candidates = []
    for c in all_variants:
        warnings = validate_structured(c, fuel, trans, cc, price)
        if warnings: continue
        
        score = max(compute_similarity(variant_name, c['name']), compute_similarity(variant_slug.replace('-', ' '), c['name']))
        
        # Block cross-edition fuzzy matching
        is_source_edition = any(kw in variant_name.lower() or kw in variant_slug.lower() for kw in EDITION_STRIP_HEURISTICS)
        is_canonical_edition = any(kw in c['name'].lower() for kw in EDITION_STRIP_HEURISTICS)
        if is_source_edition and not is_canonical_edition:
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

'''
code = code[:start_idx] + new_fuzzy_logic + code[end_idx:]

with open("knowledge_base/ingestion/common/resolver.py", "w") as f:
    f.write(code)
