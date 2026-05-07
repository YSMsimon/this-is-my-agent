from ollama import Client
from typing import List, Dict, Optional
from common.config import config
from tools.manager import tools, tool_handler, all_tools
from tools.todo import ToDoManager
from memory.db import DB
from agent.profile import ProfileManager
from colorama import Fore, Style, init as colorama_init
import itertools
import json
import threading
import time

colorama_init(autoreset=False)


class _Spinner:
    _FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

    def __init__(self):
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()
        print('\r' + ' ' * 25 + '\r', end='', flush=True)

    def _spin(self):
        for frame in itertools.cycle(self._FRAMES):
            if self._stop.is_set():
                break
            print(f'\r{Fore.CYAN}{frame} Thinking…{Style.RESET_ALL}', end='', flush=True)
            time.sleep(0.08)


class Agent:
    def __init__(self, cfg: config, tools: Optional[List] = tools, db: DB = None, user_id: str = 'default_user', is_subagent: bool = False):
        self.config = cfg
        self.tools = tools
        self.todo_manager = ToDoManager()
        self.db = db
        self.user_id = user_id
        self.is_subagent = is_subagent
        self.client = Client(host=cfg.base_url)
        self._profile = ProfileManager(db, user_id, cfg) if not is_subagent else None
        self._system_prompt = ''
        self._last_user_message = ''

    KNOWLEDGE_TOOLS = {'fetch_text', 'read_file'}

    def _chunk(self, text: str, size: int = 1500, overlap: int = 200) -> list:
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + size])
            start += size - overlap
        return chunks

    def _store_knowledge(self, args: dict, result: str):
        source_ref = args.get('url') or args.get('file_path') or ''
        source_type = 'webpage' if 'url' in args else 'file'
        for i, chunk in enumerate(self._chunk(result)):
            embedding = self.get_embedding(chunk)
            self.db.store_knowledge(self.user_id, source_type, source_ref, chunk, embedding, i)

    def get_embedding(self, text: str) -> list:
        response = self.client.embeddings(model=self.config.embedding_model, prompt=text)
        embedding = response.embedding
        return embedding

    def _build_system_prompt(self) -> str:
        if self.is_subagent:
            return self.config.subagent_system_prompt
        profile = self.db.get_user_profile(self.user_id)
        profile_text = json.dumps(profile, indent=2) if profile else "No profile yet."
        return self.config.system_prompt.format(user_profile=profile_text)

    def _build_messages(self, user_message: str) -> List[Dict]:
        if self.is_subagent:
            return [{'role': 'user', 'content': user_message}]

        history, _ = self.db.get_recent_history(self.user_id, limit=10000)

        embedding = self.get_embedding(user_message)
        knowledge = self.db.search_knowledge(embedding, top_k=5, user_id=self.user_id)

        messages = list(history)

        if knowledge:
            rag_lines = "\n\n".join(
                f"[{k['source_type']} — {k['source_ref']}]\n{k['content']}" for k in knowledge
            )
            messages.insert(0, {'role': 'system', 'content': f"Relevant knowledge:\n{rag_lines}"})

        self._save_turn({'role': 'user', 'content': user_message})
        messages.append({'role': 'user', 'content': user_message})
        return messages

    def _save_turn(self, new_messages: Dict):
        if self.is_subagent:
            return

        role = new_messages.get('role')
        content = new_messages.get('content')
        tool_call_id = new_messages.get('tool_call_id')
        self.db.add_message(self.user_id, role, content, None, tool_call_id)

        if role == 'user':
            self._last_user_message = content
        elif role == 'assistant' and self._last_user_message:
            threading.Thread(
                target=self._profile.update,
                args=(self._last_user_message, content),
                daemon=True
            ).start()

    def run(self, user_message: str) -> str:
        self._system_prompt = self._build_system_prompt()
        messages = self._build_messages(user_message)
        final_messages = self._execute(messages)
        for msg in reversed(final_messages):
            if isinstance(msg, dict) and msg.get('role') == 'assistant':
                return msg.get('content', '')
        return ''

    def _execute(self, messages: List[Dict]) -> List[Dict]:
        response = self.client.chat(
            model=self.config.model,
            messages=[{'role': 'system', 'content': self._system_prompt}] + messages,
            tools=self.tools,
            stream=True
        )

        full_content = ''
        tool_calls = None
        first_token = True
        spinner = _Spinner()
        spinner.start()

        for chunk in response:
            if chunk.message.content:
                if first_token:
                    spinner.stop()
                    print(f'{Fore.GREEN}Assistant>{Style.RESET_ALL} ', end='', flush=True)
                    first_token = False
                full_content += chunk.message.content
                print(f'{Fore.GREEN}{chunk.message.content}{Style.RESET_ALL}', end='', flush=True)
            if chunk.message.tool_calls:
                tool_calls = chunk.message.tool_calls

        if not first_token:
            print()
        else:
            spinner.stop()

        self._save_turn({'role': 'assistant', 'content': full_content})
        messages = messages + [{'role': 'assistant', 'content': full_content}]

        if not tool_calls:
            return messages

        for tool_call in tool_calls:
            tool_call_id = getattr(tool_call, 'id', None)
            name = tool_call.function.name
            args = tool_call.function.arguments
            print(f'{Fore.YELLOW}[tool: {name}]{Style.RESET_ALL}', flush=True)
            result = tool_handler[name](**args)
            if name in self.KNOWLEDGE_TOOLS and isinstance(result, str) and result.strip():
                self._store_knowledge(args, result)
            self._save_turn({'role': 'tool', 'content': f"Name: {name}, Arguments: {args}, Result: {result}", 'tool_call_id': tool_call_id})
            messages.append({'role': 'tool', 'content': f"Name: {name}, Arguments: {args}, Result: {result}", 'tool_call_id': tool_call_id})
        return self._execute(messages)
