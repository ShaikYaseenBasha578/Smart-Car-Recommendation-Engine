import urllib.request, ssl, json
from bs4 import BeautifulSoup

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    "https://www.bncap.in/vehicle/maruti-baleno-gasoline-2-airbags/",
    "https://www.bncap.in/vehicle/maruti-baleno-gasoline-6-airbags/",
    "https://www.bncap.in/vehicle/tata-punch-ev-2026/",
    "https://www.bncap.in/vehicle/tata-punch-ev/",
    "https://www.bncap.in/vehicle/tata-safari-harrier/",
    "https://www.bncap.in/vehicle/hyundai-venue/"
]

for url in urls:
    name = url.strip('/').split('/')[-1]
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, context=ctx, timeout=15).read().decode('utf-8', errors='replace')
        with open(f"scratch/{name}.html", "w") as f:
            f.write(html)
        print(f"Saved {name}.html")
    except Exception as e:
        print(f"Failed {url}: {e}")
