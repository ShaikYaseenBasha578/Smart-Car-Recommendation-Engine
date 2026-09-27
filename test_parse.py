import requests
import bs4
from urllib.parse import urljoin

url = "https://tata.cars/nexon/ice.html"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
r = requests.get(url, headers=headers)
soup = bs4.BeautifulSoup(r.text, 'html.parser')

pdfs = []
for a in soup.find_all('a', href=True):
    href = a['href']
    if '.pdf' in href.lower() or 'brochure' in href.lower() or 'download' in a.text.lower():
        pdfs.append((a.text.strip(), urljoin(url, href)))

for p in pdfs:
    print(p)
