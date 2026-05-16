import asyncio
import fcntl
import os
import shutil
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.output import ColorDepth
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from memory.db import DB
from common.config import config
from agent.loop import MainAgent
from cli.commands import CommandManager
from cli.completions import SlashCompleter, FillBgProcessor, PROMPT, STYLE
from cli.renderer import print_user_message
from cli.theme import console
from tools.manager import simple_tools


def _ensure_stdout_blocking():
    try:
        fd = sys.stdout.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if flags & os.O_NONBLOCK:
            fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
    except Exception:
        pass


async def _print_banner(cfg: config, db: DB, user_id: str):
    username = os.getenv('USER') or os.getenv('USERNAME') or 'there'

    history, _ = await db.get_recent_history(user_id, limit=20)
    last_msg = next((m['content'] for m in reversed(history) if m['role'] == 'user'), None)
    recent = f'"{last_msg[:72]}{"…" if last_msg and len(last_msg) > 72 else ""}"' if last_msg else 'No recent activity'

    # Left: welcome + recent
    left = Text()
    left.append('Welcome back, ', style='dim')
    left.append(f'{username}\n\n', style='bold green')
    left.append('Recent\n', style='dim')
    left.append(recent, style='dim italic')

    # Right: quick-reference tips
    tips = Table.grid(padding=(0, 2))
    tips.add_column(style='bold green', no_wrap=True)
    tips.add_column(style='dim')
    for cmd, desc in [
        ('/help',           'all commands'),
        ('/deep',           'multi-agent mode'),
        ('/compact',        'compress history'),
        ('/model',          'switch models'),
        ('/context-window', 'history limit'),
    ]:
        tips.add_row(cmd, desc)

    body = Columns([left, tips], equal=False, expand=True)

    console.print(Panel(
        body,
        title='[bold green]This Is My Agent[/]',
        subtitle='[dim]github.com/YSMsimon/this-is-my-agent[/]',
        border_style='green',
        padding=(1, 2),
    ))

    # Model table below the panel
    models = Table.grid(padding=(0, 2))
    models.add_column(style='dim', width=18)
    models.add_column(style='white')
    models.add_column(style='dim green')
    models.add_row('model',     cfg.model,           '')
    for label, val in [
        ('compact',   cfg.compact_model),
        ('planner',   cfg.planner_model),
        ('evaluator', cfg.evaluator_model),
        ('profile',   cfg.profile_model),
    ]:
        tag = '(= model)' if val == cfg.model else ''
        models.add_row(label, val, tag)
    console.print(models)
    console.print()


async def main():
    db  = await DB.create()
    cfg = config()
    user_id = 'default_user'

    await _print_banner(cfg, db, user_id)

    agent    = MainAgent(cfg, tools=simple_tools, db=db)
    commands = CommandManager(db, agent.user_id, cfg, agent)

    session = PromptSession(
        history=InMemoryHistory(),
        completer=SlashCompleter(),
        complete_while_typing=True,
        style=STYLE,
        include_default_pygments_style=False,
        color_depth=ColorDepth.DEPTH_8_BIT,
        input_processors=[FillBgProcessor()],
    )

    try:
        while True:
            try:
                _ph = 'Write a task or use /.'
                _ph_fill = max(0, shutil.get_terminal_size().columns - len(PROMPT) - len(_ph) - 1)
                user_input = await session.prompt_async(
                    PROMPT,
                    placeholder=HTML(f'<style fg="#555555">{_ph}{" " * _ph_fill}</style>'),
                )
            except EOFError:
                break

            _ensure_stdout_blocking()

            if not user_input.strip():
                print('\033[A\033[2K\r', end='', flush=True)
                continue

            print_user_message(user_input)

            if commands.is_command(user_input):
                await commands.handle(user_input)
                continue

            try:
                await agent.run(user_input)
            except Exception as e:
                console.print(f'[agent.error]Error:[/] {e}')

    except KeyboardInterrupt:
        pass
    finally:
        console.print('\n[dim]Exiting…[/]')
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
