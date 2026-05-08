import asyncio
import aiohttp
from bs4 import BeautifulSoup
from ddgs import DDGS


async def fetch_html(url: str) -> str:
    print(f"Fetching HTML for URL: {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10),
                               headers={"User-Agent": "Mozilla/5.0"}) as resp:
            resp.raise_for_status()
            return await resp.text()


async def fetch_text(url: str) -> str:
    print(f"Fetching text content for URL: {url}")
    html = await fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


async def web_search(query: str, max_results: int = 5) -> str:
    print(f"Performing web search for query: {query}")
    results = await asyncio.to_thread(_ddgs_search, query, max_results)
    return str(results)


def _ddgs_search(query: str, max_results: int) -> list:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))
