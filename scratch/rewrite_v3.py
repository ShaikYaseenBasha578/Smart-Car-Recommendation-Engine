import re

with open('scratch/phase8a_shadow_ingestion_v2.py', 'r') as f:
    content = f.read()

# Replace the variant extraction block
search_block = """    # Extract variants
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
                
                filtered = [c for c in cells if c not in ('YES', 'NO') and not re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \\d{4}$', c)]
                for v in filtered:
                    if v.upper() == v and len(v) > 1 and 'FAMILY' not in v.upper():
                        variants.append(v)
    explicit_variants = list(set(variants))"""

replace_block = """    def is_date(text):
        return bool(re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \\d{4}$', text.strip(), re.IGNORECASE))
    
    def is_sr_no(text):
        return text.strip().isdigit()

    variants = []
    tables = soup.find_all('table')
    
    for t in tables:
        text = t.get_text()
        if 'Ratings Applicability' in text or 'Month' in text:
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
                    
                if in_data:
                    for c in cells:
                        if c.upper() in ('YES', 'NO'): continue
                        if is_date(c): continue
                        if is_sr_no(c): continue
                        if c in ('—', '-', '–', ''): continue
                        variants.append(c)
    explicit_variants = list(set(variants))"""

content = content.replace(search_block, replace_block)

with open('scratch/phase8a_shadow_ingestion_v3.py', 'w') as f:
    f.write(content)
