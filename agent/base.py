import asyncio
import itertools
from typing import List, Dict, Optional

from ollama import AsyncClient
from colorama import Fore, Style, init as colorama_init

from common.config import config
from tools.manager import tool_handler, tools as default_tools

colorama_init(autoreset=False)

_SPINNER_FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'


async def _spin(stop: asyncio.Event):
    for frame in itertools.cycle(_SPINNER_FRAMES):
        if stop.is_set():
            break
        print(f'\r{Fore.CYAN}{frame} Thinking…{Style.RESET_ALL}', end='', flush=True)
        await asyncio.sleep(0.08)
    print('\r' + ' ' * 25 + '\r', end='', flush=True)


class Agent:
    KNOWLEDGE_TOOLS: set = set()

    def __init__(self, cfg: config, tools: Optional[List] = None):
        self.cfg = cfg
        self.tools = tools if tools is not None else default_tools
        self.client = AsyncClient(host=cfg.base_url)
        self._system_prompt = ''

    def _chunk(self, text: str, size: int = 1500, overlap: int = 200) -> list:
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + size])
            start += size - overlap
        return chunks

    async def get_embedding(self, text: str) -> list:
        response = await self.client.embeddings(model=self.cfg.embedding_model, prompt=text)
        return response.embedding

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
        spinner = asyncio.create_task(_spin(stop))

        response = await self.client.chat(
            model=self.cfg.model,
            messages=[{'role': 'system', 'content': self._system_prompt}] + messages,
            tools=self.tools,
            stream=True
        )

        full_content = ''
        tool_calls = None
        first_token = True

        async for chunk in response:
            if chunk.message.content:
                if first_token:
                    stop.set()
                    await spinner
                    print(f'{Fore.GREEN}Assistant>{Style.RESET_ALL} ', end='', flush=True)
                    first_token = False
                full_content += chunk.message.content
                print(f'{Fore.GREEN}{chunk.message.content}{Style.RESET_ALL}', end='', flush=True)
            if chunk.message.tool_calls:
                tool_calls = chunk.message.tool_calls

        if not first_token:
            print()

        stop.set()
        await spinner

        if full_content:
            await self._save_turn({'role': 'assistant', 'content': full_content})
        messages = messages + [{'role': 'assistant', 'content': full_content}]

        if not tool_calls:
            print("no tool calls")
            print(messages[-1])
            if not self._task_complete():
                messages.append({'role': 'user', 'content': 'Continue with the remaining tasks.'})
                return await self._execute(messages, _depth + 1)
            return messages

        for tool_call in tool_calls:
            tool_call_id = getattr(tool_call, 'id', None)
            name = tool_call.function.name
            args = tool_call.function.arguments
            print(f'{Fore.YELLOW}[tool: {name}]{Style.RESET_ALL}', flush=True)
            result = await self._call_tool(name, args)
            if name in self.KNOWLEDGE_TOOLS and isinstance(result, str) and result.strip():
                await self._store_knowledge(args, result)
            await self._save_turn({
                'role': 'tool',
                'content': f"Name: {name}, Arguments: {args}, Result: {result}",
                'tool_call_id': tool_call_id
            })
            messages.append({
                'role': 'tool',
                'content': f"Name: {name}, Arguments: {args}, Result: {result}",
                'tool_call_id': tool_call_id
            })

        return await self._execute(messages, _depth + 1)

    async def run(self, user_message: str) -> str:
        raise NotImplementedError
