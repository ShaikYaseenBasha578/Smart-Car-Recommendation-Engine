import requests
from bs4 import BeautifulSoup
import json
import time

def fetch_carwale_state(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    }
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        return None
        
    soup = BeautifulSoup(r.text, 'html.parser')
    for s in soup.find_all('script'):
        if s.string and 'window.__INITIAL_STATE__ =' in s.string:
            raw = s.string.split('window.__INITIAL_STATE__ =')[1].strip().split('\n\twindow.')[0]
            if raw.endswith(';'): raw = raw[:-1]
            try:
                return json.loads(raw)
            except Exception:
                pass
    return None

def extract_variant(url):
    """
    Extracts a specific variant page directly.
    """
    state = fetch_carwale_state(url)
    if not state:
        return None, 'NO_DATA'
        
    tp = state.get('trimPage')
    if not tp:
        return None, 'NO_TRIM_PAGE'
        
    # Get basic details
    vd = tp.get('versionDetail', {})
    v_name = vd.get('versionName', '')
    if not v_name:
        return None, 'NO_NAME'
        
    price = tp.get('modelPriceOverview', {}).get('price', None)
    
    # Get specs/features
    features_map = {}
    sfm = tp.get('specsFeaturesMaster', [])
    for group in sfm:
        for sub in group.get('subCategories', []):
            for item in sub.get('items', []):
                item_name = item.get('itemName')
                val = item.get('value')
                if item_name:
                    features_map[item_name] = val
                    
    return {
        'v_variant_name': v_name,
        'ex_showroom_price': price,
        'features': features_map
    }, 'SUCCESS'

if __name__ == '__main__':
    url = "https://www.carwale.com/tata-cars/harrier/smart-petrol-15l-turbo-manual/"
    data, status = extract_variant(url)
    print(status)
    if data:
        print(data['v_variant_name'])
        print(data['ex_showroom_price'])
        print(f"Extracted {len(data['features'])} features.")
