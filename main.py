import asyncio
from aioconsole import ainput
from colorama import Fore, Style

from memory.db import DB
from common.config import config
from agent.loop import Agent
from cli.commands import CommandManager
from tools.manager import all_tools


async def main():
    db = await DB.create()
    cfg = config()
    agent = Agent(cfg, tools=all_tools, db=db)
    commands = CommandManager(db, agent.user_id, cfg)
    try:
        while True:
            user_input = await ainput("User> ")
            if commands.is_command(user_input):
                await commands.handle(user_input)
                continue
            try:
                await agent.run(user_input)
            except Exception as e:
                print(f'{Fore.RED}Error: {e}{Style.RESET_ALL}')
    except KeyboardInterrupt:
        print("\nExiting...")
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
