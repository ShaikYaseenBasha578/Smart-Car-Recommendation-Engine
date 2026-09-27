import urllib.request
from bs4 import BeautifulSoup
import re, json, time, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req, context=ctx).read().decode('utf-8')
    return BeautifulSoup(html, 'html.parser')

def get_vehicle_urls():
    soup = fetch('https://www.bncap.in/vehicle-safety-ratings/')
    urls = set()
    for a in soup.find_all('a', href=True):
        if '/vehicle/' in a['href']:
            urls.add(a['href'])
    return sorted(list(urls))

results = []
urls = get_vehicle_urls()
print(f"Found {len(urls)} vehicle URLs")

for url in urls:
    try:
        time.sleep(0.5)
        soup = fetch(url)
        title_tag = soup.find('h1') or soup.find('h2')
        title = title_tag.text.strip() if title_tag else url.split('/')[-2]
        
        # Look for PDF
        pdf_url = None
        for a in soup.find_all('a', href=True):
            if '.pdf' in a['href'].lower() and ('fact' in a['href'].lower() or 'sheet' in a['href'].lower() or 'upload' in a['href'].lower()):
                pdf_url = a['href']
                break
                
        text = soup.get_text(separator=' | ', strip=True)
        
        # Look for stars (often presented as images, but maybe text?)
        # Let's extract AOP and COP scores
        aop_match = re.search(r'(\d{1,2}\.\d{1,2})\s*/\s*32(?:\.00)?', text)
        cop_match = re.search(r'(\d{1,2}\.\d{1,2})\s*/\s*49(?:\.00)?', text)
        
        # Applicability text like "Dec 2023 - Onwards"
        # Often after the title or in a specific div.
        # Let's just grab the whole text snippet containing month years
        period_match = re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+202\d\s*-\s*Onwards', text, re.IGNORECASE)
        period = period_match.group(0) if period_match else None
        
        # Let's also look for Star rating by searching for images containing 'star' or classes
        stars = set()
        for img in soup.find_all('img'):
            src = img.get('src', '').lower()
            if 'star' in src:
                # typically "5-star.png" or "4star"
                m = re.search(r'(\d)[\-_]?star', src)
                if m: stars.add(m.group(1))
        
        max_star = max(stars) if stars else None
        
        res = {
            'url': url,
            'title': title,
            'pdf_url': pdf_url,
            'aop_score': aop_match.group(1) if aop_match else None,
            'cop_score': cop_match.group(1) if cop_match else None,
            'period': period,
            'stars': max_star
        }
        results.append(res)
        print(f"Scraped: {title} (AOP: {res['aop_score']}, COP: {res['cop_score']}, Stars: {res['stars']})")
    except Exception as e:
        print(f"Error scraping {url}: {e}")

with open('scratch/bncap_raw_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Saved to scratch/bncap_raw_results.json")
