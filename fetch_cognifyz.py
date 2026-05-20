import requests
from bs4 import BeautifulSoup

url = 'https://cognifyz.com/internships/'
try:
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
    print('status', r.status_code)
    print('title=', BeautifulSoup(r.text, 'html.parser').title.string if BeautifulSoup(r.text, 'html.parser').title else None)
    soup = BeautifulSoup(r.text, 'html.parser')
    print('h1=', [h.get_text(strip=True) for h in soup.find_all('h1')])
    print('meta desc=', [m.get('content') for m in soup.find_all('meta', attrs={'name': 'description'})])
    print('og site name=', [m.get('content') for m in soup.find_all('meta', property='og:site_name')])
    print('first text snippet=', r.text[:1000])
except Exception as e:
    print('error', e)
