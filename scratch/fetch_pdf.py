import urllib.request
import ssl

url = "https://www.marutisuzuki.com/content/dam/msil/downloads/brochures/swift-brochure.pdf"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
        print(f"Status: {response.status}")
        with open('scratch/test_msil.pdf', 'wb') as f:
            f.write(response.read())
        print("Downloaded")
except Exception as e:
    print(f"Failed: {e}")
