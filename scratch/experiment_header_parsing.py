import re

def parse_header_generic(header: str):
    # Example generic header parser without hardcoded engine names
    configs = []
    
    # Clean and normalize
    header = header.replace('\n', ' ').strip()
    
    # The first token is usually the trim name (unless it contains engine info)
    tokens = header.split()
    if not tokens: return []
    
    trim_match = re.match(r'^([a-zA-Z0-9\+\-\(\)]+)', tokens[0])
    trim = trim_match.group(1) if trim_match else tokens[0]
    
    # Sometimes trim is two words like "VXi (O)"
    if len(tokens) > 1 and tokens[1].startswith('(') and tokens[1].endswith(')'):
        trim = f"{trim} {tokens[1]}"
        
    blocks = re.split(r'\s*&\s*', header)
    
    for block in blocks:
        # Extract engine (e.g. 1.2L, 1.0L Turbo, 1.5 l CRDi)
        engine = None
        # look for digit.digit followed by optional L/l and optional words before MT/AT etc
        eng_match = re.search(r'(\d\.\d\s*[a-zA-Z\s]*?)(?=\b(?:MT|AT|AMT|CVT|DCT|AGS|CNG|Petrol|Diesel)\b|$)', block, re.IGNORECASE)
        if eng_match:
            engine = eng_match.group(1).strip()
            # clean up trailing slashes or junk
            engine = re.sub(r'[/\\+]$', '', engine).strip()
            if engine.lower() == trim.lower(): # prevent matching trim if it looks like engine
                engine = None
        
        # Extract powertrain combinations
        # Looking for things like MT/AMT, MT/MT CNG, AT
        trans_matches = re.finditer(r'\b(MT|AT|AMT|CVT|DCT|AGS|iVT)(?:\s+(CNG))?\b', block, re.IGNORECASE)
        
        combos = []
        for m in trans_matches:
            trans = m.group(1).upper()
            fuel = "CNG" if m.group(2) else "Petrol"
            combos.append((trans, fuel))
            
        # Fallbacks
        if not combos:
            if 'CNG' in block.upper():
                combos.append(("MT", "CNG"))
            else:
                combos.append(("MT", "Petrol"))
                
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
    "ZXi+ 5MT/5AMT"
]
for h in headers:
    print(f"--- {h} ---")
    for c in parse_header_generic(h):
        print(c)

