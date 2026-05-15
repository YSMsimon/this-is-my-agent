import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.crawl import web_search


async def main():
    query = "Current time in toronto"

    results = await web_search(query, max_results= 10, page=2)
    print(results)


if __name__ == "__main__":
    asyncio.run(main())
