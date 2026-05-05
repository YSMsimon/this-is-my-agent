import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

def fetch_html(url: str) -> str:
    resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.text

def fetch_text(url: str) -> str:
    print(f"Fetching text content for URL: {url}")
    resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

def web_search(query: str, max_results: int = 5) -> str:
    print(f"Performing web search for query: {query}")
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return str(results)   # returns list of {title, href, body}


if __name__ == "__main__":
    pass