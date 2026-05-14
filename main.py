import asyncio
import fcntl
import os
import sys
from aioconsole import ainput
from colorama import Fore, Style

from memory.db import DB
from common.config import config
from agent.loop import MainAgent
from cli.commands import CommandManager
from tools.manager import simple_tools


def _ensure_stdout_blocking():
    """aioconsole sets stdout O_NONBLOCK when it wires up its async streams.
    Regular print() calls fail with EAGAIN when the pty buffer fills up.
    Restore blocking so our sync prints always succeed."""
    try:
        fd = sys.stdout.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if flags & os.O_NONBLOCK:
            fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
    except Exception:
        pass


async def main():
    db = await DB.create()
    cfg = config()
    agent = MainAgent(cfg, tools=simple_tools, db=db)
    commands = CommandManager(db, agent.user_id, cfg, agent)
    try:
        while True:
            user_input = await ainput("User> ")
            _ensure_stdout_blocking()
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
