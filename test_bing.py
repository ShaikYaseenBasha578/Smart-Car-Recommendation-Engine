import requests
import bs4
import base64
from urllib.parse import urlparse, parse_qs

def search_bing(query):
    url = f"https://www.bing.com/search?q={requests.utils.quote(query)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    r = requests.get(url, headers=headers)
    soup = bs4.BeautifulSoup(r.text, 'html.parser')
    results = []
    for a in soup.select('h2 a'):
        href = a.get('href')
        if '/ck/a' in href:
            u = parse_qs(urlparse(href).query).get('u', [''])[0]
            if u.startswith('a1'):
                u = u[2:]
            try:
                # Add padding
                u += '=' * (-len(u) % 4)
                decoded = base64.b64decode(u).decode('utf-8')
                results.append(decoded)
            except Exception as e:
                pass
        else:
            results.append(href)
    return results

print(search_bing("site:tatamotors.com Tata Nexon"))
