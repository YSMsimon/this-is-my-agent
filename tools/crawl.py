import asyncio
import locale
import requests
import trafilatura
import fitz
from ddgs import DDGS

def _detect_region() -> str:
    loc = locale.getdefaultlocale()[0] or 'en_US'
    try:
        lang, country = loc.lower().split('_', 1)
        return f"{country}-{lang}"
    except ValueError:
        return 'us-en'

async def fetch_html(url: str) -> str:
    return await asyncio.to_thread(_fetch_html_sync, url)

def _fetch_html_sync(url: str) -> str:
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.text

async def fetch_text(url: str) -> str:
    return await asyncio.to_thread(_fetch_text_sync, url)

def _fetch_text_sync(url: str) -> str:
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        return f"Error fetching {url}: {e}"
    if "application/pdf" in resp.headers.get("Content-Type", ""):
        try:
            doc = fitz.open(stream=resp.content, filetype="pdf")
            text = "\n\n".join(page.get_text() for page in doc).strip()
            if not text:
                return "This PDF appears to be scanned or image-based, and text extraction failed."
            return text
        except Exception as e:
            return f"Error reading PDF: {e}"

    text = trafilatura.extract(resp.text, include_comments=False, include_tables=True)
    return text

async def web_search(query: str, max_results: int = 10, page: int = 1) -> str:
    results = await asyncio.to_thread(_ddgs_search, query, max_results, page)
    return str(results)

def _ddgs_search(query: str, max_results: int, page: int) -> list:
    _REGION = _detect_region()
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results, safesearch='off', region=_REGION, page=page))
