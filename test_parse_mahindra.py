import requests
import bs4
from urllib.parse import urljoin, urlparse, parse_qs
import base64

def search_bing(query):
    url = f"https://www.bing.com/search?q={requests.utils.quote(query)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    r = requests.get(url, headers=headers)
    soup = bs4.BeautifulSoup(r.text, 'html.parser')
    for a in soup.select('h2 a'):
        href = a.get('href')
        if '/ck/a' in href:
            u = parse_qs(urlparse(href).query).get('u', [''])[0]
            if u.startswith('a1'): u = u[2:]
            try:
                u += '=' * (-len(u) % 4)
                decoded = base64.b64decode(u).decode('utf-8')
                if 'mahindra.com' in decoded: return decoded
            except: pass
    return None

url = search_bing("Mahindra Scorpio-N official site")
print("Found URL:", url)

if url:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    r = requests.get(url, headers=headers)
    soup = bs4.BeautifulSoup(r.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '.pdf' in href.lower() or 'brochure' in href.lower():
            print(a.text.strip(), urljoin(url, href))
