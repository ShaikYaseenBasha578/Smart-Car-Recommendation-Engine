with open("knowledge_base/ingestion/common/resolver.py", "r") as f:
    code = f.read()

import re

# Split by "def compute_similarity" and "def validate_structured"
start_idx = code.find("def compute_similarity")
end_idx = code.find("def validate_structured")

new_compute_similarity = '''
def compute_similarity(s1, s2):
    if not s1 or not s2: return 0.0
    from difflib import SequenceMatcher
    import re
    
    def normalize_tokens(s):
        s = s.replace('-', ' ').lower()
        s = s.replace('manual', 'mt').replace('automatic', 'at')
        s = re.sub(r'\\b\d\.\d+l\\b', '', s)
        s = s.replace('turbo', '').replace('vtvt', '').replace('mpi', '').replace('crdi', '')
        s = s.replace('+', ' plus ')
        s = s.replace('(o)', ' optional ')
        
        tokens = set(s.split())
        config_words = {'petrol', 'diesel', 'cng', 'ev', 'mt', 'at', 'cvt', 'dct', 'amt', 'awd', '4x4', 'fwd', 'rwd', 'hybrid', 'electric'}
        
        identity_tokens = tokens - config_words
        if not identity_tokens:
            return tokens
        return identity_tokens
        
    tokens1 = normalize_tokens(s1)
    tokens2 = normalize_tokens(s2)
    
    if not tokens1 or not tokens2: return 0.0
    
    if tokens1 == tokens2: return 1.0
    
    overlap = len(tokens1.intersection(tokens2))
    if overlap == 0: return 0.0
    
    if overlap == len(tokens1) or overlap == len(tokens2): return 0.8
    
    str1 = ' '.join(sorted(list(tokens1)))
    str2 = ' '.join(sorted(list(tokens2)))
    return SequenceMatcher(None, str1, str2).ratio()

'''

code = code[:start_idx] + new_compute_similarity + code[end_idx:]


old_loop = '''    best_match = None
    best_score = 0
    for c in all_variants:'''

new_loop = '''    best_matches = []
    best_score = 0
    for c in all_variants:'''
    
code = code.replace(old_loop, new_loop)

old_update = '''        if score > best_score:
            best_score = score
            best_match = c'''

new_update = '''        if score > best_score:
            best_score = score
            best_matches = [c]
        elif score == best_score:
            best_matches.append(c)'''

code = code.replace(old_update, new_update)

old_check = '''    if best_match and best_score > 0.5:
        warnings = validate_structured(best_match, fuel, trans, cc, price)
        if warnings: return best_match['id'], 'needs_review', None
        return best_match['id'], 'resolved', None'''

new_check = '''    if best_matches and best_score > 0.5:
        if len(best_matches) > 1:
            return None, 'unresolved', None
        best_match = best_matches[0]
        warnings = validate_structured(best_match, fuel, trans, cc, price)
        if warnings: return best_match['id'], 'needs_review', None
        return best_match['id'], 'resolved', None'''
        
code = code.replace(old_check, new_check)

with open("knowledge_base/ingestion/common/resolver.py", "w") as f:
    f.write(code)
