import requests
import bs4
url = "https://www.skoda-auto.co.in/models/slavia/slavia"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
r = requests.get(url, headers=headers)
print("Status:", r.status_code)
soup = bs4.BeautifulSoup(r.text, 'html.parser')
links = soup.find_all('a', href=True)
brochures = [a['href'] for a in links if 'brochure' in a['href'].lower() or 'brochure' in a.text.lower()]
print("Brochure links:", brochures)
pdfs = [a['href'] for a in links if '.pdf' in a['href'].lower()]
print("PDF links:", pdfs)
