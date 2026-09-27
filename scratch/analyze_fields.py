import re
from knowledge_base.ingestion.oem.field_map_oem import OEM_FIELD_RULES

def robust_key_normalize(k):
    k = k.lower().strip()
    
    # 1. Punctuation replacements
    k = k.replace('-', ' ')
    k = k.replace('/', ' ')
    k = k.replace('&', ' and ')
    
    # 2. Bracket normalization
    k = re.sub(r'\(.*?\)', ' ', k)
    
    # 3. Common trailing/noise words for exact specs
    noise = ['with ebd', 'highline', 'system', 'program', 'control', 'assist', 'level 2']
    
    # Just normalize spaces first
    k = re.sub(r'\s+', ' ', k).strip()
    
    return k

examples = [
    "electronic stability control (esc)",
    "tyre pressure monitoring system(tpms) highline",
    "abs(anti-lock braking system) with ebd",
    "abs with ebd",
    "tpms - tyre pressure monitoring system",
    "hyundai smartsense (level 2 adas)"
]

for e in examples:
    print(f"'{e}' -> '{robust_key_normalize(e)}'")
