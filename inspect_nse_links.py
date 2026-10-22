import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

url = "https://www.nseindia.com/static/market-data/securities-available-for-trading"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,*/*",
})

response = session.get(url, timeout=30)
print("NSE status:", response.status_code)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

for a in soup.find_all("a", href=True):
    label = a.get_text(" ", strip=True)
    link = urljoin(url, a["href"])
    if any(word in (label + " " + link).lower()
           for word in ["symbol", "equity", "securit"]):
        print(f"{label or '[no label]'} -> {link}")
