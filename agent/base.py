import asyncio
import itertools
import json
import threading
from typing import List, Dict, Optional

from colorama import Fore, Style, init as colorama_init

from adapters import Adapter
from common.config import config
from tools.manager import tool_handler, tools as default_tools

colorama_init(autoreset=False)


_SPINNER_FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'


async def _spin(stop: asyncio.Event, done: threading.Event | None = None):
    for frame in itertools.cycle(_SPINNER_FRAMES):
        if stop.is_set():
            break
        print(f'\r{Fore.CYAN}{frame} Thinking…{Style.RESET_ALL}', end='', flush=True)
        await asyncio.sleep(0.08)
    print('\r' + ' ' * 25 + '\r', end='', flush=True)
    if done:
        done.set()


class Agent:
    KNOWLEDGE_TOOLS: set = set()

    def __init__(self, cfg: config, tools: Optional[List] = None):
        self.cfg = cfg
        self.tools = tools if tools is not None else default_tools
        self._system_prompt = ''
        self.adapter = Adapter(cfg)

    def _chunk(self, text: str, size: int = 1500, overlap: int = 200) -> list:
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + size])
            start += size - overlap
        return chunks

    async def get_embedding(self, text: str) -> list:
        return self.adapter.embed(text, model=self.cfg.embedding_model)

    def _task_complete(self) -> bool:
        return True

    async def _save_turn(self, msg: Dict):
        pass

    async def _store_knowledge(self, args: dict, result: str):
        pass

    async def _call_tool(self, name: str, args: dict) -> str:
        return await tool_handler[name](**args)

    async def _execute(self, messages: List[Dict], _depth: int = 0) -> List[Dict]:
        if _depth >= 30:
            return messages

        stop = asyncio.Event()
        spinner_done = threading.Event()
        spinner = asyncio.create_task(_spin(stop, spinner_done))
        loop = asyncio.get_running_loop()
        first_chunk = True

        def on_chunk(chunk: str):
            nonlocal first_chunk
            if first_chunk:
                first_chunk = False
                loop.call_soon_threadsafe(stop.set)
                spinner_done.wait(timeout=1.0)
                print(f'{Fore.GREEN}Assistant>{Style.RESET_ALL} ', end='', flush=True)
            print(f'{Fore.GREEN}{chunk}{Style.RESET_ALL}', end='', flush=True)

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.adapter.complete(
                    messages=[{'role': 'system', 'content': self._system_prompt}] + messages,
                    model=self.cfg.model,
                    tools=self.tools or None,
                    stream=True,
                    on_chunk=on_chunk,
                )
            )
        except RuntimeError as e:
            stop.set()
            await spinner
            print(f'\n{Fore.RED}{e}{Style.RESET_ALL}')
            return messages
        except Exception as e:
            stop.set()
            await spinner
            print(f'\n{Fore.RED}LLM error: {type(e).__name__}: {str(e)[:200]}{Style.RESET_ALL}')
            return messages

        stop.set()
        await spinner

        if response.content:
            print()

        full_content = response.content
        full_reasoning = response.reasoning
        tool_calls = response.tool_calls

        # Build assistant message — include tool_calls and reasoning_content when
        # present so subsequent turns are correctly linked for strict providers.
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
            print(f'{Fore.YELLOW}[tool: {name}]{Style.RESET_ALL}', flush=True)
            result = await self._call_tool(name, args)
            if name in self.KNOWLEDGE_TOOLS and isinstance(result, str) and result.strip():
                await self._store_knowledge(args, result)
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
