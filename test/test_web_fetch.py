import asyncio
import sys
from tools.crawl import fetch_text, web_search



async def test_html_fetch():
    url = "https://github.com/YSMsimon/this-is-my-agent"
    result = await fetch_text(url)
    return result


async def test_pdf_fetch():
    url = ""
    result = await fetch_text(url)
    return result

async def main():
    #print(await test_html_fetch())
    await test_pdf_fetch()


asyncio.run(main())
