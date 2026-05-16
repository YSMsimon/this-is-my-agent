import asyncio
import itertools
import json
from typing import List, Dict, Optional

from colorama import Fore, Style, init as colorama_init

from adapters import Adapter
from common.config import config
from tools.manager import tool_handler, tools as default_tools
from cli.renderer import StreamRenderer

colorama_init(autoreset=False)


_SPINNER_FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'


async def _spin(stop: asyncio.Event):
    for frame in itertools.cycle(_SPINNER_FRAMES):
        if stop.is_set():
            break
        print(f'\r{Fore.CYAN}{frame} Thinking…{Style.RESET_ALL}', end='', flush=True)
        await asyncio.sleep(0.08)
    # no cleanup here — caller clears the line


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
            stop = asyncio.Event()
            spinner = asyncio.create_task(_spin(stop))
            renderer = StreamRenderer()

            def on_chunk(chunk: str) -> None:
                renderer.on_chunk(chunk)

            try:
                response = await self.adapter.complete(
                    messages=[{'role': 'system', 'content': self._system_prompt}] + messages,
                    model=self.cfg.model,
                    tools=self.tools or None,
                    stream=True,
                    on_chunk=on_chunk,
                )
            except RuntimeError as e:
                stop.set()
                renderer.stop()
                await spinner
                if str(e) == 'context_window_exceeded':
                    print(f'\r{" " * 25}\r\n{Fore.YELLOW}Context window exceeded.{Style.RESET_ALL}')
                    print(f'  • Run {Fore.CYAN}/compact{Style.RESET_ALL} to summarise and compress your history')
                    print(f'  • Or {Fore.CYAN}/clear-history{Style.RESET_ALL} to start fresh (cannot be undone)')
                else:
                    print(f'\r{" " * 25}\r\n{Fore.RED}{e}{Style.RESET_ALL}')
                return messages
            except Exception as e:
                stop.set()
                renderer.stop()
                await spinner
                print(f'\r{" " * 25}\r\n{Fore.RED}LLM error: {type(e).__name__}: {str(e)[:200]}{Style.RESET_ALL}')
                return messages

            stop.set()
            await spinner
            renderer.stop()

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
                print(f'{Fore.YELLOW}[tool: {name}]{Style.RESET_ALL}', flush=True)
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
