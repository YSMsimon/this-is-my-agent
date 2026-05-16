import asyncio

from memory.db import DB
from common.config import config
from agent.loop import MainAgent
from cli.app import AgentApp
from tools.manager import simple_tools


async def main():
    db = await DB.create()
    cfg = config()
    agent = MainAgent(cfg, tools=simple_tools, db=db)
    app = AgentApp(cfg, agent, db)
    try:
        await app.run_async()
    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
