import urllib.request
from bs4 import BeautifulSoup
import re, json, ssl
from concurrent.futures import ThreadPoolExecutor

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req, context=ctx, timeout=10).read().decode('utf-8')
    return BeautifulSoup(html, 'html.parser')

def scrape_url(url):
    try:
        soup = fetch(url)
        title_tag = soup.find('h1') or soup.find('h2')
        title = title_tag.text.strip() if title_tag else url.split('/')[-2]
        
        pdf_url = None
        for a in soup.find_all('a', href=True):
            if '.pdf' in a['href'].lower() and ('fact' in a['href'].lower() or 'sheet' in a['href'].lower() or 'upload' in a['href'].lower()):
                pdf_url = a['href']
                break
                
        text = soup.get_text(separator=' | ', strip=True)
        aop_match = re.search(r'(\d{1,2}\.\d{1,2})\s*/\s*32(?:\.00)?', text)
        cop_match = re.search(r'(\d{1,2}\.\d{1,2})\s*/\s*49(?:\.00)?', text)
        period_match = re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+202\d\s*-\s*Onwards', text, re.IGNORECASE)
        
        return {
            'url': url,
            'title': title,
            'pdf_url': pdf_url,
            'aop_score': aop_match.group(1) if aop_match else None,
            'cop_score': cop_match.group(1) if cop_match else None,
            'period': period_match.group(0) if period_match else None
        }
    except Exception as e:
        return {'url': url, 'title': url.split('/')[-2], 'error': str(e)}

urls = [
"https://www.bncap.in/vehicle/citroen-basalt/",
"https://www.bncap.in/vehicle/citroen-c3-aircross-5-seater/",
"https://www.bncap.in/vehicle/honda-amaze-3rd-gen/",
"https://www.bncap.in/vehicle/hyundai-tucson-gasoline/",
"https://www.bncap.in/vehicle/hyundai-venue/",
"https://www.bncap.in/vehicle/kia-seltos/",
"https://www.bncap.in/vehicle/kia-syros/",
"https://www.bncap.in/vehicle/mahindra-be-6/",
"https://www.bncap.in/vehicle/mahindra-thar-roxx/",
"https://www.bncap.in/vehicle/mahindra-xev-9e/",
"https://www.bncap.in/vehicle/mahindra-xuv-3xo/",
"https://www.bncap.in/vehicle/mahindra-xuv-400-ev/",
"https://www.bncap.in/vehicle/mahindra-xuv-7xo/",
"https://www.bncap.in/vehicle/maruti-baleno-gasoline-2-airbags/",
"https://www.bncap.in/vehicle/maruti-baleno-gasoline-6-airbags/",
"https://www.bncap.in/vehicle/maruti-brezza/",
"https://www.bncap.in/vehicle/maruti-dzire-gasoline/",
"https://www.bncap.in/vehicle/maruti-suzuki-e-vitara/",
"https://www.bncap.in/vehicle/maruti-suzuki-invicto/",
"https://www.bncap.in/vehicle/maruti-suzuki-victoris/",
"https://www.bncap.in/vehicle/nissan-tekton/",
"https://www.bncap.in/vehicle/renault-duster/",
"https://www.bncap.in/vehicle/skoda-kylaq/",
"https://www.bncap.in/vehicle/tata-altroz/",
"https://www.bncap.in/vehicle/tata-curvv-ev/",
"https://www.bncap.in/vehicle/tata-curvv/",
"https://www.bncap.in/vehicle/tata-harrier-ev/",
"https://www.bncap.in/vehicle/tata-nexon-ev/",
"https://www.bncap.in/vehicle/tata-nexon/",
"https://www.bncap.in/vehicle/tata-punch-ev-2026/",
"https://www.bncap.in/vehicle/tata-punch-ev/",
"https://www.bncap.in/vehicle/tata-punch/",
"https://www.bncap.in/vehicle/tata-safari-harrier/",
"https://www.bncap.in/vehicle/tata-sierra/",
"https://www.bncap.in/vehicle/toyota-innova-hycross/",
"https://www.bncap.in/vehicle/vinfast-vf6/",
"https://www.bncap.in/vehicle/vinfast-vf7/"
]

results = []
with ThreadPoolExecutor(max_workers=10) as executor:
    for res in executor.map(scrape_url, urls):
        results.append(res)
        print(f"Done: {res.get('title')}")

with open('scratch/bncap_raw_results.json', 'w') as f:
    json.dump(results, f, indent=2)
