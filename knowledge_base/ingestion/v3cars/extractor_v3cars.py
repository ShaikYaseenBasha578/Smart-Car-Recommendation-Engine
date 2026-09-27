import requests
from bs4 import BeautifulSoup
import re
import json

def fetch_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        return BeautifulSoup(r.text, 'html.parser'), r.text
    return None, None

def extract_model_page(make_slug, model_slug):
    """
    Extracts base variants, prices, and model-level warranty from the main model page.
    Also returns links to the variant-explained articles.
    """
    url = f"https://www.v3cars.com/{make_slug}-cars/{model_slug}"
    soup, raw = fetch_soup(url)
    if not soup:
        return {'status': 'NO_DATA', 'variants': [], 'model_level': {}, 'variant_articles': []}
        
    tables = soup.find_all('table')
    variants = []
    warranty = None
    
    for t in tables:
        rows = t.find_all('tr')
        if not rows: continue
        headers = [c.get_text(strip=True).lower() for c in rows[0].find_all(['th', 'td'])]
        
        # Variants & Prices Table
        if 'variants' in headers and 'ex-showroomprice' in headers:
            for tr in rows[1:]:
                cells = [c.get_text(strip=True) for c in tr.find_all(['th', 'td'])]
                if len(cells) >= 2:
                    variants.append({
                        'v_variant_name': cells[0],
                        'ex_showroom_price': cells[1]
                    })
                    
        # Standard Warranty Table
        if 'standard warranty' in headers:
            if len(rows) > 0 and len(rows[0].find_all(['th', 'td'])) >= 2:
                warranty = rows[0].find_all(['th', 'td'])[1].get_text(strip=True)

    # Find variant-explained articles
    article_links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/variant-explained/' in href and model_slug in href:
            article_links.add("https://www.v3cars.com" + href if href.startswith('/') else href)
            
    return {
        'status': 'SUCCESS_COMPLETE' if variants else 'NO_DATA',
        'variants': variants,
        'model_level': {'warranty': warranty} if warranty else {},
        'variant_articles': list(article_links)
    }

def parse_feature_inheritance(soup, model_slug):
    """
    Parses the "variant-explained" article tables to build cumulative feature sets for each trim.
    """
    tables = soup.find_all('table')
    trim_features = {}
    base_trim = None
    
    # Heuristic to clean model name from title
    model_pattern = model_slug.replace('-', ' ').upper()
    
    for t in tables:
        rows = t.find_all('tr')
        if not rows: continue
        title = rows[0].find(['th', 'td']).get_text(strip=True).upper()
        
        # 1. Base Model Standard Features
        if 'BASE MODEL' in title or 'STANDARD FEATURES' in title:
            # e.g. HYUNDAI CRETA EBASE MODEL STANDARD FEATURES
            # Extract trim: string between model name and BASE MODEL
            idx = title.find(model_pattern)
            if idx != -1:
                trim_str = title[idx + len(model_pattern):].split('BASE')[0].strip()
                if trim_str:
                    base_trim = trim_str
                    trim_features[base_trim] = set()
                    for tr in rows[2:]: # Skip title and category header
                        for c in tr.find_all(['th', 'td']):
                            txt = c.get_text(strip=True)
                            if txt: trim_features[base_trim].add(txt)
                            
        # 2. Features Over X
        elif 'FEATURES OVER' in title:
            # e.g. HYUNDAI CRETA EXFEATURES OVER E
            idx = title.find(model_pattern)
            if idx != -1:
                sub = title[idx + len(model_pattern):]
                parts = sub.split('FEATURES OVER')
                if len(parts) == 2:
                    current_trim = parts[0].strip()
                    parent_trim = parts[1].strip()
                    
                    if current_trim not in trim_features:
                        trim_features[current_trim] = set()
                        
                    # Inherit parent features
                    if parent_trim in trim_features:
                        trim_features[current_trim].update(trim_features[parent_trim])
                        
                    # Add new features
                    for tr in rows[2:]:
                        for c in tr.find_all(['th', 'td']):
                            txt = c.get_text(strip=True)
                            if txt: trim_features[current_trim].add(txt)
                            
    return trim_features

def build_variant_payloads(make_slug, model_slug):
    page_data = extract_model_page(make_slug, model_slug)
    if page_data['status'] == 'NO_DATA':
        return [], [], page_data['status']
        
    all_trim_features = {}
    
    # Build cumulative features from all articles
    for url in page_data['variant_articles']:
        soup, _ = fetch_soup(url)
        if soup:
            trim_f = parse_feature_inheritance(soup, model_slug)
            # Merge into master dict
            for t, feats in trim_f.items():
                if t not in all_trim_features:
                    all_trim_features[t] = set()
                all_trim_features[t].update(feats)
                
    # Map back to specific variants
    # Example table variant: "Creta E1.5L Petrol Manual"
    # We need to extract the "E" part.
    model_name_prefix = model_slug.replace('-', ' ').title() # e.g. Creta
    
    observations = []
    
    for v in page_data['variants']:
        raw_name = v['v_variant_name']
        price = v['ex_showroom_price']
        
        # Try to find which trim this variant belongs to
        # Sort trim names by length descending to match "SX (O)" before "SX"
        matched_trim = None
        features = list()
        
        for t in sorted(all_trim_features.keys(), key=len, reverse=True):
            # Check if trim exists in the variant name
            # E.g. "Creta E1.5L" contains "E". To avoid matching "E" inside "Petrol", we check word boundaries or specific formatting.
            # V3Cars format: "Creta E1.5L" -> "Creta " + trim + "1.5L" (often missing space)
            # Or "Creta SX Tech1.5L"
            
            # Simple heuristic: remove model name, then check if it starts with trim
            name_stripped = raw_name.lower().replace(model_name_prefix.lower(), '').strip()
            if name_stripped.startswith(t.lower()):
                matched_trim = t
                features = list(all_trim_features[t])
                break
                
        obs = {
            'v_variant_name': raw_name,
            'ex_showroom_price': price,
            'features': features,
            'matched_trim': matched_trim
        }
        observations.append(obs)
        
    model_obs = []
    if page_data['model_level']:
        model_obs.append({
            'raw_name': f"{make_slug} {model_slug} - Model Level",
            'payload': {
                'scope': 'MODEL',
                'warranty': page_data['model_level'].get('warranty')
            }
        })
        
    return observations, model_obs, page_data['status']

if __name__ == '__main__':
    v, m, s = build_variant_payloads('hyundai', 'creta')
    print("Status:", s)
    print(f"Variants extracted: {len(v)}")
    if v: print(json.dumps(v[:3], indent=2))
    print(f"Model obs: {len(m)}")
    if m: print(json.dumps(m, indent=2))
