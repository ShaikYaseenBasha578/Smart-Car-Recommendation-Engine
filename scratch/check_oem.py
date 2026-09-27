import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

urls = {
    "Maruti Arena": "https://www.marutisuzuki.com/",
    "Maruti Nexa": "https://www.nexaexperience.com/",
    "Hyundai": "https://www.hyundai.com/in/en"
}

for name, url in urls.items():
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            html = response.read().decode('utf-8')
            print(f"{name}: SUCCESS ({len(html)} bytes) - Status: {response.status}")
    except Exception as e:
        print(f"{name}: FAILED - {e}")
