import urllib.request
import urllib.parse
import re
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def search(query):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req, context=ctx).read().decode('utf-8')
        links = re.findall(r'href="(//duckduckgo\.com/l/\?uddg=[^"]+)"', html)
        decoded_links = []
        for link in links:
            raw_url = urllib.parse.unquote(link.split('uddg=')[1].split('&')[0])
            decoded_links.append(raw_url)
        return decoded_links
    except Exception as e:
        return [str(e)]

print("Thar ROXX:")
for l in search("Mahindra Thar ROXX brochure pdf")[:5]: print(l)
print("\nPunch:")
for l in search("Tata Punch brochure pdf site:cars.tatamotors.com")[:5]: print(l)
print("\nAura:")
for l in search("Hyundai Aura brochure pdf site:hyundai.com")[:5]: print(l)
print("\nDzire:")
for l in search("Maruti Dzire brochure pdf site:marutisuzuki.com")[:5]: print(l)
