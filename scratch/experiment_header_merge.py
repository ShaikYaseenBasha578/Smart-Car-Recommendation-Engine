import sys
import os
import re
sys.path.append(os.getcwd())

def is_header_continuation(row):
    # It's a header if the first column is empty OR if it contains powertrain keywords
    first_col = row[0].strip().lower()
    
    # If the first column is empty, it's a header continuation.
    if not first_col or first_col in ["variant", "variants", "powertrain", "transmission", "engine"]:
        return True
        
    # Or if a significant number of columns contain MT/AT/CNG
    pt_count = sum(1 for c in row if re.search(r'\b(MT|AT|AMT|CVT|DCT|AGS|iVT|CNG|Petrol|Diesel|Turbo)\b', c, re.IGNORECASE))
    
    # If more than 30% of the columns have powertrain words, it's a header
    if len([c for c in row if c]) > 0 and pt_count / len([c for c in row if c]) > 0.3:
        return True
        
    return False

# Test with Fronx
r1 = ['', 'Sigma 1.2L', 'Delta 1.2L', 'Delta+ 1.2L MT/AMT &', 'Zeta', 'Alpha']
r2 = ['', 'MT/MT CNG', 'MT/MT CNG/AMT', '1.0L Turbo MT', '1.0L Turbo MT/AT', '1.0L Turbo MT/AT']
r3 = ['Electrically Foldable ORVMs', '—', '\uf0fc', '\uf0fc', '\uf0fc', '\uf0fc (Auto)']

print(is_header_continuation(r2))
print(is_header_continuation(r3))

