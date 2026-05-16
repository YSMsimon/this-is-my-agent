import asyncio
import fcntl
import json
import os
import sys
from typing import List, Dict, Optional

from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.text import Text

from adapters import Adapter
from common.config import config
from tools.manager import tool_handler, tools as default_tools
from cli.theme import console


def _ensure_stdout_blocking():
    try:
        fd = sys.stdout.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if flags & os.O_NONBLOCK:
            fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
    except Exception:
        pass


def _print_tool_call(name: str, args: dict) -> None:
    t = Text()
    t.append('  ⚙ ', style='dim cyan')
    t.append(name, style='bold cyan')
    if args:
        short = '  ' + ',  '.join(
            f'{k}={repr(v)[:50]}' for k, v in list(args.items())[:3]
        )
        t.append(short, style='dim')
    console.print(t)


class Agent:
    _silent: bool = False  # when True: no spinner, no streaming, no stdout (parallel background workers)

    def __init__(self, cfg: config, tools: Optional[List] = None):
        self.cfg = cfg
        self.tools = tools if tools is not None else default_tools
        self._system_prompt = ''
        self.adapter = Adapter(cfg)
        self.session_input_tokens = 0
        self.session_output_tokens = 0

    def _task_complete(self) -> bool:
        return True

    async def _save_turn(self, msg: Dict):
        pass

    async def _call_tool(self, name: str, args: dict) -> str:
        return await tool_handler[name](**args)

    async def _execute(self, messages: List[Dict], _depth: int = 0) -> List[Dict]:
        if _depth >= 30:
            return messages

        if self._silent:
            try:
                response = await self.adapter.complete(
                    messages=[{'role': 'system', 'content': self._system_prompt}] + messages,
                    model=self.cfg.model,
                    tools=self.tools or None,
                )
                self.session_input_tokens += response.input_tokens
                self.session_output_tokens += response.output_tokens
            except Exception:
                return messages
        else:
            _buf: list[str] = []
            # transient=True: always erase the Live area on stop.
            # If there was streamed content we re-print it below — this avoids
            # leaving ghost spinner frames when a turn produces only tool calls.
            _live = Live(
                Spinner('dots', text=' Thinking…', style='dim cyan'),
                refresh_per_second=15,
                console=console,
                transient=True,
            )

            def on_chunk(chunk: str) -> None:
                _buf.append(chunk)
                _live.update(Markdown(''.join(_buf)))

            _ensure_stdout_blocking()
            _live.start()
            try:
                response = await self.adapter.complete(
                    messages=[{'role': 'system', 'content': self._system_prompt}] + messages,
                    model=self.cfg.model,
                    tools=self.tools or None,
                    stream=True,
                    on_chunk=on_chunk,
                )
            except RuntimeError as e:
                _live.stop()
                if str(e) == 'context_window_exceeded':
                    console.print('\n[agent.warn]Context window exceeded.[/]')
                    console.print('  • Run [bold cyan]/compact[/] to summarise and compress your history')
                    console.print('  • Or [bold cyan]/clear-history[/] to start fresh')
                else:
                    console.print(f'\n[agent.error]{e}[/]')
                return messages
            except Exception as e:
                _live.stop()
                console.print(f'\n[agent.error]LLM error: {type(e).__name__}: {str(e)[:200]}[/]')
                return messages

            _ensure_stdout_blocking()
            _live.stop()
            # Don't re-print here — we only render content permanently in the
            # no-tool-calls branch below.  For turns that include tool calls,
            # the streaming view was transient (good: shows thinking, then clears).

            self.session_input_tokens += response.input_tokens
            self.session_output_tokens += response.output_tokens

        full_content = response.content
        full_reasoning = response.reasoning
        tool_calls = response.tool_calls

        assistant_msg: Dict = {'role': 'assistant', 'content': full_content or None}
        if full_reasoning:
            assistant_msg['reasoning_content'] = full_reasoning
        if tool_calls:
            assistant_msg['tool_calls'] = tool_calls

        if full_content:
            await self._save_turn({'role': 'assistant', 'content': full_content})

        messages = messages + [assistant_msg]

        if not tool_calls:
            # Final turn — permanently render the content now that we know
            # no tool calls follow (avoids double-print on Continue loops).
            if not self._silent and full_content:
                console.print(Markdown(full_content))
            if not self._task_complete():
                messages.append({'role': 'user', 'content': 'Continue with the remaining tasks.'})
                return await self._execute(messages, _depth + 1)
            return messages

        for tc in tool_calls:
            name = tc['function']['name']
            try:
                args = json.loads(tc['function']['arguments']) if tc['function']['arguments'] else {}
            except json.JSONDecodeError:
                args = {}
            tool_call_id = tc['id']
            if not self._silent:
                _ensure_stdout_blocking()
                _print_tool_call(name, args)
            try:
                result = await self._call_tool(name, args)
            except Exception as e:
                result = f"Tool error ({name}): {e}"
            await self._save_turn({
                'role': 'tool',
                'content': f"Name: {name}, Arguments: {args}, Result: {result}",
                'tool_call_id': tool_call_id,
            })
            messages.append({
                'role': 'tool',
                'tool_call_id': tool_call_id,
                'content': str(result),
            })

        return await self._execute(messages, _depth + 1)

    async def run(self, user_message: str) -> str:
        raise NotImplementedError
