import requests
import re
url = "https://www.skoda-auto.co.in/shopping/slavia-download-a-brochure"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r = requests.get(url, headers=headers)
pdfs = re.findall(r'https?://[^\s\"\'<>]*\.pdf', r.text)
print("PDFs in source:", pdfs)
