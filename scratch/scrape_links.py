import urllib.request
import re
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    "https://auto.mahindra.com/suv/thar-roxx",
    "https://cars.tatamotors.com/punch/ice.html",
    "https://www.hyundai.com/in/en/find-a-car/aura/highlights.html",
    "https://www.marutisuzuki.com/dzire"
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, context=ctx).read().decode('utf-8')
        links = re.findall(r'href="([^"]+\.pdf)"', html, re.IGNORECASE)
        print(f"[{url}]")
        for l in set(links): print("  ", l)
    except Exception as e:
        print(f"[{url}] Error: {e}")
