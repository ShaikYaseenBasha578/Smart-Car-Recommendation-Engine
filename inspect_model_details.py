import requests
from bs4 import BeautifulSoup
import json

url = "https://www.carwale.com/tata-cars/harrier/"
headers = {'User-Agent': 'Mozilla/5.0'}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')
for s in soup.find_all('script'):
    if s.string and 'window.__INITIAL_STATE__ =' in s.string:
        raw = s.string.split('window.__INITIAL_STATE__ =')[1].strip().split('\n\twindow.')[0]
        if raw.endswith(';'): raw = raw[:-1]
        data = json.loads(raw)
        
        md = data.get('modelPage', {}).get('modelDetails', {})
        print("Keys in modelDetails:", md.keys())
        
        if 'variantList' in md:
            print(f"\nFound variantList with {len(md['variantList'])} items.")
            v0 = md['variantList'][0]
            print(json.dumps(v0, indent=2)[:1000])
        break
