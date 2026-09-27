import re

def parse_header_string(header: str):
    """
    Takes a string like 'Delta 1.2L MT/MT CNG/AMT'
    and returns a list of dictionaries with trim, engine, trans, fuel.
    """
    configs = []
    
    # Split by '&' if multiple major blocks exist (like Delta+ 1.2L MT/AMT & 1.0L Turbo MT)
    blocks = header.split('&')
    
    # We assume the first word is the trim
    tokens = header.split()
    trim = tokens[0]
    if trim.endswith('+'): trim = trim # e.g. Delta+
    
    for block in blocks:
        block = block.strip()
        # Find Engine
        engine = None
        if "1.2" in block: engine = "1.2 L K-Series"
        if "1.0" in block or "Turbo" in block: engine = "1.0 L Turbo Boosterjet"
        
        # Find Trans/Fuel
        # Matches patterns like MT/MT CNG/AMT
        trans_part = re.search(r'(MT.*|AT.*|AMT.*)', block)
        if trans_part:
            t_str = trans_part.group(1)
            parts = t_str.split('/')
            for p in parts:
                p = p.strip()
                trans = "MT"
                fuel = "Petrol"
                
                if "MT" in p: trans = "MT"
                if "AMT" in p: trans = "AMT"
                if "AT" in p: trans = "AT"
                
                if "CNG" in p: fuel = "CNG"
                
                configs.append({
                    "variant": trim,
                    "engine": engine,
                    "trans": trans,
                    "fuel": fuel
                })
    return configs

print(parse_header_string("Sigma 1.2L MT/MT CNG"))
print(parse_header_string("Delta 1.2L MT/MT CNG/AMT"))
print(parse_header_string("Delta+ 1.2L MT/AMT & 1.0L Turbo MT"))
