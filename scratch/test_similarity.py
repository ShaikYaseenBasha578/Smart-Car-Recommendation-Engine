def compute_similarity(s1, s2):
    s1, s2 = s1.lower(), s2.lower()
    if s1 == s2: return 1.0
    
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
            
    overlap = len(tokens1.intersection(tokens2))
    if overlap == len(tokens1) or overlap == len(tokens2): 
        unmatched_id = len(id1.symmetric_difference(id2))
        return 0.8 - (unmatched_id * 0.05)
        
    from difflib import SequenceMatcher
    str1 = ' '.join(sorted(list(tokens1)))
    str2 = ' '.join(sorted(list(tokens2)))
    return SequenceMatcher(None, str1, str2).ratio()

print("VXi vs VXi Petrol MT:", compute_similarity("VXi", "VXi Petrol MT"))
print("VXi vs VXi (O) Petrol MT:", compute_similarity("VXi", "VXi (O) Petrol MT"))
