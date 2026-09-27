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
    print(f"\n--- {f} ---")
    with open(f) as fh: soup = BeautifulSoup(fh.read(), 'html.parser')
    
    for t in soup.find_all('table'):
        text = t.get_text()
        if 'Ratings Applicability' in text or 'Month' in text:
            headers = []
            variants = []
            in_data = False
            for r in t.find_all('tr'):
                # use td and th, maintaining colspan logic?
                # Actually colspan makes mapping hard. Let's just flatten the row.
                cells = []
                for c in r.find_all(['th', 'td']):
                    colspan = int(c.get('colspan', 1))
                    for _ in range(colspan):
                        cells.append(c.get_text(strip=True))
                
                if not any(cells): continue
                
                if any('Disclaimer' in c or 'Revision' in c or 'addition of variants' in c for c in cells if c):
                    in_data = False
                    continue
                    
                has_yes_no = any(c.upper() in ('YES', 'NO') for c in cells if c)
                has_date = any(is_date(c) for c in cells if c)
                
                if has_yes_no or has_date:
                    in_data = True
                    
                if not in_data:
                    headers.append(cells)
                else:
                    for i, c in enumerate(cells):
                        if not c: continue
                        if c.upper() in ('YES', 'NO'): continue
                        if is_date(c): continue
                        if is_sr_no(c): continue
                        if c in ('—', '-', '–', ''): continue
                        
                        # Gather column headers for this index
                        col_headers = []
                        for hrow in headers:
                            if i < len(hrow) and hrow[i] and hrow[i] not in ('Sr No.', 'Month & Year of Assessment', 'Ratings Applicability', 'HYUNDAI \u2013 VENUE', 'Punch.ev 2026', 'MARUTI BALENO \u2013 GASOLINE'):
                                col_headers.append(hrow[i])
                        
                        variants.append({"variant": c, "context": " | ".join(col_headers)})
                        
            print("HEADERS:")
            for h in headers: print(h)
            print("VARIANTS:")
            for v in variants[:10]: print(v)
