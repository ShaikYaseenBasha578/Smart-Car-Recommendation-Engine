import re

def parse_header_generic(header: str):
    configs = []
    header = header.replace('\n', ' ').strip()
    tokens = header.split()
    if not tokens: return []
    
    trim = tokens[0]
    if len(tokens) > 1 and tokens[1].startswith('(') and tokens[1].endswith(')'):
        trim = f"{trim} {tokens[1]}"
        
    blocks = re.split(r'\s*&\s*', header)
    
    for block in blocks:
        engine = None
        eng_match = re.search(r'(\d\.\d\s*[a-zA-Z\s]*?)(?=(?:\b\d?(?:MT|AT|AMT|CVT|DCT|AGS|iVT)\b|\b(?:CNG|Petrol|Diesel)\b|$))', block, re.IGNORECASE)
        if eng_match:
            engine = eng_match.group(1).strip()
            engine = re.sub(r'[/\\+]$', '', engine).strip()
            if not engine or engine.lower() == trim.lower():
                engine = None
        
        # Match e.g. "MT", "5MT", "MT CNG", "AMT"
        trans_matches = re.finditer(r'\b\d?(MT|AT|AMT|CVT|DCT|AGS|iVT)(?:\s+(CNG))?\b', block, re.IGNORECASE)
        
        combos = []
        for m in trans_matches:
            trans = m.group(1).upper()
            fuel = "CNG" if m.group(2) else "Petrol"
            # Some text has "VXi CNG 5MT" where CNG is before MT. Let's catch that too.
            combos.append((trans, fuel))
            
        # Catch "CNG 5MT"
        cng_before = re.finditer(r'\bCNG\s+\d?(MT|AT|AMT|CVT|DCT|AGS|iVT)\b', block, re.IGNORECASE)
        for m in cng_before:
            trans = m.group(1).upper()
            combos.append((trans, "CNG"))
            
        if not combos:
            if 'CNG' in block.upper():
                combos.append(("MT", "CNG"))
            else:
                combos.append(("MT", "Petrol"))
                
        # Deduplicate
        combos = list(dict.fromkeys(combos))
        
        for trans, fuel in combos:
            configs.append({
                "variant": trim,
                "engine": engine if engine else None,
                "trans": trans,
                "fuel": fuel
            })
            
    return configs

headers = [
    "Sigma 1.2L MT/MT CNG",
    "Delta+ 1.2L MT/AMT & 1.0L Turbo MT",
    "Zeta 1.0L Turbo MT/AT",
    "Alpha 1.0L Turbo MT/AT",
    "VXi 5MT/5AMT VXi CNG 5MT",
    "ZXi+ 5MT/5AMT",
    "LXi"
]
for h in headers:
    print(f"--- {h} ---")
    for c in parse_header_generic(h):
        print(c)

