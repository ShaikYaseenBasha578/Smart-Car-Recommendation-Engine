import requests
import os

os.makedirs('knowledge_base/tests/fixtures', exist_ok=True)
url = 'https://www.91wheels.com/cars/hyundai/creta'
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        with open('knowledge_base/tests/fixtures/creta_rsc_payload.html', 'w') as f:
            f.write(r.text)
        print("Saved Creta fixture")
except Exception as e:
    print("Error:", e)
