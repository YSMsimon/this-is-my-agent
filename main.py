import asyncio
import fcntl
import os
import re
import sys
from aioconsole import ainput
from colorama import Fore, Style

from memory.db import DB
from common.config import config
from agent.loop import MainAgent
from cli.commands import CommandManager
from tools.manager import simple_tools

_ANSI = re.compile(r'\x1b\[[0-9;]*m')

def _vlen(s: str) -> int:
    return len(_ANSI.sub('', s))

def _pad(s: str, width: int) -> str:
    return s + ' ' * max(0, width - _vlen(s))


def _ensure_stdout_blocking():
    try:
        fd = sys.stdout.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if flags & os.O_NONBLOCK:
            fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
    except Exception:
        pass


async def _print_banner(cfg: config, db: DB, user_id: str):
    C = Fore.GREEN
    Y = Fore.YELLOW
    W = Fore.WHITE
    R = Style.RESET_ALL
    DIM = '\033[2m'

    LW = 33
    RW = 39

    username = os.getenv('USER') or os.getenv('USERNAME') or 'there'
    github   = 'github.com/YSMsimon/this-is-my-agent'

    history, _ = await db.get_recent_history(user_id, limit=20)
    last_msg = next((m['content'] for m in reversed(history) if m['role'] == 'user'), None)
    if last_msg:
        max_chars = RW - 3
        trimmed = last_msg[:max_chars] + ('…' if len(last_msg) > max_chars else '')
        recent = f'"{trimmed}"'
    else:
        recent = 'No recent activity'

    def clip(text: str, width: int) -> str:
        """Truncate text to fit visible width, preserving ANSI codes."""
        if _vlen(text) <= width:
            return text
        # strip ANSI, truncate plain, re-apply reset
        plain = _ANSI.sub('', text)
        return plain[:width - 1] + '…' + R

    def cell(text: str, width: int) -> str:
        return _pad(f' {clip(text, width)} ', width + 2)

    def both(left: str, right: str) -> str:
        return f'{C}│{R}{cell(left, LW)}{C}│{R}{cell(right, RW)}{C}│{R}'

    def rdiv() -> str:
        return f'{C}│{R}{" " * (LW + 2)}{C}├{"─" * (RW + 2)}┤{R}'

    top = f'{C}╭{"─" * (LW + 2)}┬{"─" * (RW + 2)}╮{R}'
    bot = f'{C}╰{"─" * (LW + 2)}┴{"─" * (RW + 2)}╯{R}'

    total = LW + RW + 6
    dashes = '─' * max(0, total - len(f'── This Is My Agent  {github}  '))
    print(f'{C}── {W}This Is My Agent{R}  {DIM}{github}{R}  {C}{dashes}{R}')

    # box
    print(top)
    print(both(f'{W}Welcome back, {Y}{username}!{R}',  f'{Y}Tips for getting started{R}'))
    print(both('',                                      f'{DIM}/help{R}   show all commands'))
    print(both('',                                      f'{DIM}/deep{R}   multi-agent deep mode'))
    print(both('',                                      f'{DIM}/compact{R}   compress history'))
    print(both('',                                      f'{DIM}/apikey{R}   update API keys'))
    print(both('',                                      f'{DIM}/context-window{R}   history limit'))
    print(both('',                                      ''))
    print(rdiv())
    print(both('',                                      f'{Y}Recent activity{R}'))
    print(both('',                                      f'{DIM}{recent}{R}'))
    print(both('',                                      ''))
    print(bot)
    print()

    def mrow(label: str, val: str) -> str:
        tag = f' {DIM}(default){R}' if val == cfg.model and label != 'MODEL' else ''
        return f'  {DIM}{label:<18}{R}{W}{val}{R}{tag}'

    print(mrow('MODEL',           cfg.model))
    print(mrow('COMPACT_MODEL',   cfg.compact_model))
    print(mrow('PLANNER_MODEL',   cfg.planner_model))
    print(mrow('EVALUATOR_MODEL', cfg.evaluator_model))
    print(mrow('PROFILE_MODEL',   cfg.profile_model))
    print()


async def main():
    db = await DB.create()
    cfg = config()
    user_id = 'default_user'
    await _print_banner(cfg, db, user_id)
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
