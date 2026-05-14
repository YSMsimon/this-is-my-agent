import asyncio
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS


async def fetch_html(url: str) -> str:
    return await asyncio.to_thread(_fetch_html_sync, url)


def _fetch_html_sync(url: str) -> str:
    resp = requests.get(url, timeout= 15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.text


async def fetch_text(url: str) -> str:
    try:
        html = await fetch_html(url)
    except Exception as e:
        return f"Error fetching {url}: {e}"
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


async def web_search(query: str, max_results: int = 5) -> str:
    results = await asyncio.to_thread(_ddgs_search, query, max_results)
    return str(results)


def _ddgs_search(query: str, max_results: int) -> list:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))
