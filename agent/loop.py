import asyncio
import itertools
import json
from typing import List, Dict, Optional

from ollama import AsyncClient
from colorama import Fore, Style, init as colorama_init

from common.config import config
from tools.manager import tools, tool_handler, all_tools
from tools.todo import ToDoManager, PlanItemStatus
from memory.db import DB
from agent.profile import ProfileManager

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
    def __init__(self, cfg: config, tools: Optional[List] = tools, db: DB = None,
                 user_id: str = 'default_user', is_subagent: bool = False):
        self.config = cfg
        self.tools = tools
        self.todo_manager = ToDoManager()
        self.db = db
        self.user_id = user_id
        self.is_subagent = is_subagent
        self.client = AsyncClient(host=cfg.base_url)
        self._profile = ProfileManager(db, user_id, cfg) if not is_subagent else None
        self._system_prompt = ''
        self._last_user_message = ''

    KNOWLEDGE_TOOLS = {'fetch_text', 'read_file'}

    def _task_complete(self) -> bool:
        if not self.todo_manager.items:
            return True
        return all(i.status == PlanItemStatus.COMPLETED for i in self.todo_manager.items)

    def _chunk(self, text: str, size: int = 1500, overlap: int = 200) -> list:
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + size])
            start += size - overlap
        return chunks

    async def _store_knowledge(self, args: dict, result: str):
        source_ref = args.get('url') or args.get('file_path') or ''
        source_type = 'webpage' if 'url' in args else 'file'
        for i, chunk in enumerate(self._chunk(result)):
            embedding = await self.get_embedding(chunk)
            await self.db.store_knowledge(self.user_id, source_type, source_ref, chunk, embedding, i)

    async def get_embedding(self, text: str) -> list:
        response = await self.client.embeddings(model=self.config.embedding_model, prompt=text)
        return response.embedding

    async def _build_system_prompt(self) -> str:
        if self.is_subagent:
            return self.config.subagent_system_prompt
        profile = await self.db.get_user_profile(self.user_id)
        profile_text = json.dumps(profile, indent=2) if profile else "No profile yet."
        return self.config.system_prompt.format(user_profile=profile_text)

    async def _build_messages(self, user_message: str) -> List[Dict]:
        if self.is_subagent:
            return [{'role': 'user', 'content': user_message}]

        history, embedding = await asyncio.gather(
            self.db.get_recent_history(self.user_id, limit=10000),
            self.get_embedding(user_message)
        )
        history, _ = history
        knowledge = await self.db.search_knowledge(embedding, top_k=5, user_id=self.user_id)

        messages = list(history)

        if knowledge:
            rag_lines = "\n\n".join(
                f"[{k['source_type']} — {k['source_ref']}]\n{k['content']}" for k in knowledge
            )
            messages.insert(0, {'role': 'system', 'content': f"Relevant knowledge:\n{rag_lines}"})

        await self._save_turn({'role': 'user', 'content': user_message})
        messages.append({'role': 'user', 'content': user_message})
        return messages

    async def _save_turn(self, new_messages: Dict):
        if self.is_subagent:
            return

        role = new_messages.get('role')
        content = new_messages.get('content')
        tool_call_id = new_messages.get('tool_call_id')
        await self.db.add_message(self.user_id, role, content, None, tool_call_id)

        if role == 'user':
            self._last_user_message = content
        elif role == 'assistant' and self._last_user_message:
            asyncio.create_task(self._profile.update(self._last_user_message, content))

    async def run(self, user_message: str) -> str:
        self.todo_manager = ToDoManager()
        self._system_prompt = await self._build_system_prompt()
        messages = await self._build_messages(user_message)
        final_messages = await self._execute(messages)
        for msg in reversed(final_messages):
            if isinstance(msg, dict) and msg.get('role') == 'assistant':
                return msg.get('content', '')
        return ''

    async def _execute(self, messages: List[Dict], _depth: int = 0) -> List[Dict]:
        if _depth >= 30:
            return messages

        stop = asyncio.Event()
        spinner = asyncio.create_task(_spin(stop))

        response = await self.client.chat(
            model=self.config.model,
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
            if not self._task_complete():
                messages.append({'role': 'user', 'content': 'Continue with the remaining tasks.'})
                return await self._execute(messages, _depth + 1)
            return messages

        for tool_call in tool_calls:
            tool_call_id = getattr(tool_call, 'id', None)
            name = tool_call.function.name
            args = tool_call.function.arguments
            print(f'{Fore.YELLOW}[tool: {name}]{Style.RESET_ALL}', flush=True)
            if name == 'to_do':
                result = self.todo_manager.to_do(**args)
            else:
                result = await tool_handler[name](**args)
            if name in self.KNOWLEDGE_TOOLS and isinstance(result, str) and result.strip():
                await self._store_knowledge(args, result)
            await self._save_turn({'role': 'tool', 'content': f"Name: {name}, Arguments: {args}, Result: {result}", 'tool_call_id': tool_call_id})
            messages.append({'role': 'tool', 'content': f"Name: {name}, Arguments: {args}, Result: {result}", 'tool_call_id': tool_call_id})

        return await self._execute(messages, _depth + 1)
