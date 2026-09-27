import requests
import bs4
url = "https://www.skoda-auto.co.in/shopping/slavia-download-a-brochure"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
r = requests.get(url, headers=headers)
soup = bs4.BeautifulSoup(r.text, 'html.parser')
links = soup.find_all('a', href=True)
pdfs = [a['href'] for a in links if '.pdf' in a['href'].lower()]
print("PDF links:", pdfs)
