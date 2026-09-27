import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    'https://www.marutisuzuki.com/content/dam/msil/downloads/brochures/swift-brochure.pdf',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
)

try:
    with urllib.request.urlopen(req, context=ctx) as response:
        with open('scratch/test.pdf', 'wb') as f:
            f.write(response.read())
    print("Success")
except Exception as e:
    print(e)
