import asyncio
import itertools
import json
from typing import List, Dict, Optional

import litellm
from colorama import Fore, Style, init as colorama_init

from common.config import config
from tools.manager import tool_handler, tools as default_tools

colorama_init(autoreset=False)

litellm.drop_params = True
litellm.suppress_debug_info = True

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
        self._system_prompt = ''

    def _chunk(self, text: str, size: int = 1500, overlap: int = 200) -> list:
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + size])
            start += size - overlap
        return chunks

    async def get_embedding(self, text: str) -> list:
        response = await litellm.aembedding(model=self.cfg.embedding_model, input=[text])
        item = response.data[0]
        return item['embedding'] if isinstance(item, dict) else item.embedding

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

        response = await litellm.acompletion(
            model=self.cfg.model,
            messages=[{'role': 'system', 'content': self._system_prompt}] + messages,
            tools=self.tools if self.tools else None,
            stream=True,
        )

        full_content = ''
        full_reasoning = ''
        tool_calls_raw = {}  # index -> {id, name, arguments}
        first_token = True

        try:
            async for chunk in response:
                delta = chunk.choices[0].delta

                reasoning = getattr(delta, 'reasoning_content', None)
                if reasoning:
                    full_reasoning += reasoning

                if delta.content:
                    if first_token:
                        stop.set()
                        await spinner
                        print(f'{Fore.GREEN}Assistant>{Style.RESET_ALL} ', end='', flush=True)
                        first_token = False
                    full_content += delta.content
                    print(f'{Fore.GREEN}{delta.content}{Style.RESET_ALL}', end='', flush=True)

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_raw:
                            tool_calls_raw[idx] = {'id': '', 'name': '', 'arguments': ''}
                        if tc_delta.id:
                            tool_calls_raw[idx]['id'] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_raw[idx]['name'] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_raw[idx]['arguments'] += tc_delta.function.arguments

        except litellm.RateLimitError as e:
            stop.set()
            await spinner
            print(f'\n{Fore.RED}Rate limit reached: {e.message if hasattr(e, "message") else e}{Style.RESET_ALL}')
            return messages
        except Exception as e:
            stop.set()
            await spinner
            print(f'\n{Fore.RED}LLM error: {type(e).__name__}: {str(e)[:200]}{Style.RESET_ALL}')
            return messages

        if not first_token:
            print()

        stop.set()
        await spinner

        tool_calls = [tool_calls_raw[i] for i in sorted(tool_calls_raw)] if tool_calls_raw else []

        # Build assistant message — include tool_calls and reasoning_content when
        # present so subsequent turns are correctly linked for strict providers.
        assistant_msg: Dict = {'role': 'assistant', 'content': full_content or None}
        if full_reasoning:
            assistant_msg['reasoning_content'] = full_reasoning
        if tool_calls:
            assistant_msg['tool_calls'] = [
                {
                    'id': tc['id'],
                    'type': 'function',
                    'function': {'name': tc['name'], 'arguments': tc['arguments']},
                }
                for tc in tool_calls
            ]

        if full_content:
            await self._save_turn({'role': 'assistant', 'content': full_content})

        messages = messages + [assistant_msg]

        if not tool_calls:
            if not self._task_complete():
                messages.append({'role': 'user', 'content': 'Continue with the remaining tasks.'})
                return await self._execute(messages, _depth + 1)
            return messages

        for tc in tool_calls:
            name = tc['name']
            try:
                args = json.loads(tc['arguments']) if tc['arguments'] else {}
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
