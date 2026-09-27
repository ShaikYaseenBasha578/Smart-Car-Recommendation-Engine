from bs4 import BeautifulSoup
import re, json

files = [
    'scratch/maruti-baleno-gasoline-2-airbags.html',
    'scratch/maruti-baleno-gasoline-6-airbags.html',
    'scratch/tata-punch-ev-2026.html',
    'scratch/tata-punch-ev.html',
    'scratch/tata-safari-harrier.html',
    'scratch/hyundai-venue.html'
]

def is_date(text):
    return bool(re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}$', text.strip(), re.IGNORECASE))

def is_sr_no(text):
    return text.strip().isdigit()

for f in files:
    print(f"\n--- {f} ---")
    with open(f) as fh: soup = BeautifulSoup(fh.read(), 'html.parser')
    
    variants = []
    for t in soup.find_all('table'):
        text = t.get_text()
        if 'Ratings Applicability' in text or 'Month' in text:
            in_data = False
            current_app_flag = None
            for r in t.find_all('tr'):
                cells = [c.get_text(strip=True) for c in r.find_all(['th', 'td']) if c.get_text(strip=True)]
                if not cells: continue
                
                if any('Disclaimer' in c or 'Revision' in c or 'addition of variants' in c for c in cells):
                    in_data = False
                    current_app_flag = None
                    continue
                    
                has_yes_no = any(c.upper() in ('YES', 'NO') for c in cells)
                has_date = any(is_date(c) for c in cells)
                
                if has_yes_no or has_date:
                    in_data = True
                    
                if in_data:
                    # Update propagating flag if we see one
                    for c in cells:
                        if c.upper() in ('YES', 'NO'):
                            current_app_flag = c.upper()
                            
                    for c in cells:
                        if c.upper() in ('YES', 'NO'): continue
                        if is_date(c): continue
                        if is_sr_no(c): continue
                        if c in ('—', '-', '–', ''): continue
                        variants.append((c, current_app_flag))
    
    # Print distinct
    res = {}
    for v, flag in variants:
        res[v] = flag
    print(list(res.items())[:5])
