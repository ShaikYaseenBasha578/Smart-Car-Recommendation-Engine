with open("knowledge_base/ingestion/common/resolver.py", "r") as f:
    code = f.read()

import re
start_idx = code.find("def compute_similarity")
end_idx = code.find("def validate_structured")

new_compute_similarity = '''
def compute_similarity(s1, s2):
    if not s1 or not s2: return 0.0
    from difflib import SequenceMatcher
    import re
    
    def get_tokens(s):
        s = s.replace('-', ' ').lower()
        s = s.replace('manual', 'mt').replace('automatic', 'at')
        s = re.sub(r'\\b\d\.\d+l\\b', '', s)
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

'''

code = code[:start_idx] + new_compute_similarity + code[end_idx:]

with open("knowledge_base/ingestion/common/resolver.py", "w") as f:
    f.write(code)
