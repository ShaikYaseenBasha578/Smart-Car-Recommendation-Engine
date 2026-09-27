import sqlite3, re
from bs4 import BeautifulSoup
import scratch.phase8a_shadow_ingestion as phase8a

def extract_variants_from_soup(soup):
    variants = []
    tables = soup.find_all('table')
    
    in_variant_section = False
    for t in tables:
        text = t.get_text()
        if 'The variants to which' in text or 'Ratings Applicability' in text and 'Month' in text:
            in_variant_section = True
            
        if in_variant_section:
            if 'Child restraint' in text or 'Dynamic score' in text:
                break
            
            for row in t.find_all('tr'):
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th']) if td.get_text(strip=True)]
                if not cells: continue
                if 'Month &' in cells[-1] or 'Revision' in cells[0] or 'Disclaimer' in cells[0] or 'The addition' in cells[0]:
                    continue
                
                filtered = [c for c in cells if c not in ('YES', 'NO') and not re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}$', c)]
                
                for v in filtered:
                    if v.upper() == v and len(v) > 1 and 'FAMILY' not in v.upper():
                        variants.append(v)
    return list(set(variants))

# Verify it works
with open('scratch/sample_baleno_2ab.html') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')
    print(extract_variants_from_soup(soup))
