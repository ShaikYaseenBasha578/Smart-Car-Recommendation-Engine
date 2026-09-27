from bs4 import BeautifulSoup
import re, json

files = [
    'scratch/maruti-baleno-gasoline-2-airbags.html',
    'scratch/tata-safari-harrier.html',
    'scratch/tata-punch-ev-2026.html',
    'scratch/hyundai-venue.html'
]

def is_date(text):
    return bool(re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}$', text.strip(), re.IGNORECASE))

def is_sr_no(text):
    return text.strip().isdigit()

for f in files:
    print(f"\n{'='*50}\nMODEL: {f}\n{'='*50}")
    with open(f) as fh: soup = BeautifulSoup(fh.read(), 'html.parser')
    
    for t in soup.find_all('table'):
        text = t.get_text()
        if 'Ratings Applicability' in text or 'Month' in text:
            headers = []
            extracted = []
            excluded = []
            in_data = False
            for r in t.find_all('tr'):
                cells = [c.get_text(strip=True) for c in r.find_all(['th', 'td']) if c.get_text(strip=True)]
                if not cells: continue
                
                if any('Disclaimer' in c or 'Revision' in c or 'addition of variants' in c for c in cells):
                    in_data = False
                    continue
                    
                has_yes_no = any(c.upper() in ('YES', 'NO') for c in cells)
                has_date = any(is_date(c) for c in cells)
                
                if has_yes_no or has_date:
                    in_data = True
                    
                if not in_data:
                    headers.append(cells)
                    excluded.extend([(c, "Header cell (precedes data grid)") for c in cells])
                else:
                    for c in cells:
                        if c.upper() in ('YES', 'NO'):
                            excluded.append((c, "Applicability flag"))
                        elif is_date(c):
                            excluded.append((c, "Date column"))
                        elif is_sr_no(c):
                            excluded.append((c, "Serial Number"))
                        elif c in ('—', '-', '–', ''):
                            excluded.append((c, "Empty/Null cell"))
                        else:
                            extracted.append(c)
                            
            print("\n--- SOURCE TABLE HEADERS ---")
            for h in headers: print(h)
            
            print("\n--- EXTRACTED VARIANT/CONFIGURATION CELLS ---")
            for v in extracted[:15]: print(v)
            if len(extracted) > 15: print(f"... and {len(extracted)-15} more.")
            
            print("\n--- EXCLUDED CELLS AND WHY ---")
            for ex in excluded[:15]: print(f" '{ex[0]}' -> {ex[1]}")
            if len(excluded) > 15: print(f"... and {len(excluded)-15} more.")
