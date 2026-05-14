import asyncio
import json
from typing import List, Dict, Optional

from colorama import Fore, Style

from common.config import config
from tools.manager import simple_tools, executor_tools, tool_handler
from tools.todo import ToDoManager, PlanItemStatus
from memory.db import DB
from agent.base import Agent
from agent.profile import ProfileManager


class MainAgent(Agent):
    KNOWLEDGE_TOOLS = {'fetch_text', 'read_file'}

    def __init__(self, cfg: config, tools: Optional[List] = None,
                 db: DB = None, user_id: str = 'default_user'):
        super().__init__(cfg, tools if tools is not None else simple_tools)
        self.db = db
        self.user_id = user_id
        self.todo_manager = ToDoManager()
        self._profile = ProfileManager(db, user_id, cfg, self.adapter)
        self._last_user_message = ''
        self.mode = 'simple'
        self.context_window: int | None = None  # None = no limit; loaded lazily from DB
        self._context_window_loaded = False

    def _task_complete(self) -> bool:
        if not self.todo_manager.items:
            return True
        return all(i.status == PlanItemStatus.COMPLETED for i in self.todo_manager.items)

    async def _call_tool(self, name: str, args: dict) -> str:
        if name == 'to_do':
            return self.todo_manager.to_do(**args)
        return await tool_handler[name](**args)

    async def _store_knowledge(self, args: dict, result: str):
        source_ref = args.get('url') or args.get('file_path') or ''
        source_type = 'webpage' if 'url' in args else 'file'
        for i, chunk in enumerate(self._chunk(result)):
            if not chunk.strip():
                continue
            embedding = await self.get_embedding(chunk)
            if not embedding:
                continue
            await self.db.store_knowledge(self.user_id, source_type, source_ref, chunk, embedding, i)

    async def _save_turn(self, msg: Dict):
        role = msg.get('role')
        content = msg.get('content')
        tool_call_id = msg.get('tool_call_id')
        await self.db.add_message(self.user_id, role, content, None, tool_call_id)

        if role == 'user':
            self._last_user_message = content
        elif role == 'assistant' and self._last_user_message:
            asyncio.create_task(self._profile.update(self._last_user_message, content))

    async def _build_system_prompt(self) -> str:
        profile = await self.db.get_user_profile(self.user_id)
        profile_text = json.dumps(profile, indent=2) if profile else "No profile yet."
        return self.cfg.system_prompt.format(user_profile=profile_text)

    async def _build_messages(self, user_message: str) -> List[Dict]:
        if not self._context_window_loaded:
            self.context_window = await self.db.get_context_window(self.user_id)
            self._context_window_loaded = True

        limit = self.context_window if self.context_window is not None else 10000
        history, embedding = await asyncio.gather(
            self.db.get_recent_history(self.user_id, limit=limit),
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

    def _print_token_summary(self, turn_input: int, turn_output: int):
        dim = '\033[2m'
        reset = Style.RESET_ALL
        total = self.session_input_tokens + self.session_output_tokens
        print(
            f"{dim}  ↑ {turn_input:,} ↓ {turn_output:,} tokens"
            f"  ·  session ↑ {self.session_input_tokens:,} ↓ {self.session_output_tokens:,}"
            f"  (total {total:,}){reset}"
        )

    async def run(self, user_message: str) -> str:
        if self.mode == 'deep':
            return await self._run_deep(user_message)
        return await self._run_simple(user_message)

    async def _run_simple(self, user_message: str) -> str:
        self.todo_manager = ToDoManager()
        self._system_prompt = await self._build_system_prompt()
        messages = await self._build_messages(user_message)
        tokens_before = (self.session_input_tokens, self.session_output_tokens)
        final_messages = await self._execute(messages)
        turn_in = self.session_input_tokens - tokens_before[0]
        turn_out = self.session_output_tokens - tokens_before[1]
        if turn_in or turn_out:
            self._print_token_summary(turn_in, turn_out)
        for msg in reversed(final_messages):
            if isinstance(msg, dict) and msg.get('role') == 'assistant':
                return msg.get('content', '')
        return ''

    async def _run_deep(self, user_message: str) -> str:
        from agent.planner import PlannerAgent
        from agent.evaluator import EvaluatorAgent

        print(f'{Fore.CYAN}[Deep] Planning...{Style.RESET_ALL}')
        tasks = await PlannerAgent(self.cfg).run(user_message)
        print(f'{Fore.CYAN}[Deep] {len(tasks)} task(s):{Style.RESET_ALL}')
        for i, t in enumerate(tasks):
            print(f'  {i+1}. {t}')

        results = await self._run_executors(tasks, user_message)

        for round_num in range(3):
            print(f'{Fore.CYAN}[Deep] Evaluating (round {round_num + 1})...{Style.RESET_ALL}')
            evaluation = await EvaluatorAgent(self.cfg).evaluate(user_message, results)
            if evaluation.passed:
                print(f'{Fore.GREEN}[Deep] Evaluation passed.{Style.RESET_ALL}')
                break
            if not evaluation.issues:
                break
            print(f'{Fore.YELLOW}[Deep] {len(evaluation.issues)} issue(s), spawning fix executors...{Style.RESET_ALL}')
            results.extend(await self._run_executors(evaluation.issues, user_message))

        return await self._synthesize(user_message, results)

    async def _run_executors(self, tasks: list[str], context: str) -> list[dict]:
        from agent.executor import ExecutorAgent

        async def run_one(task: str, idx: int) -> dict:
            print(f'{Fore.YELLOW}[Executor {idx+1}] {task}{Style.RESET_ALL}')
            try:
                result = await ExecutorAgent(self.cfg, tools=executor_tools).run(task, context)
            except Exception as e:
                result = f"Executor error: {e}"
            print(f'{Fore.YELLOW}[Executor {idx+1}] done.{Style.RESET_ALL}')
            return {'task': task, 'result': result}

        return list(await asyncio.gather(*[run_one(t, i) for i, t in enumerate(tasks)]))

    async def _synthesize(self, user_message: str, results: list[dict]) -> str:
        summary = "\n\n".join(f"Task: {r['task']}\nResult: {r['result']}" for r in results)
        tokens_before = (self.session_input_tokens, self.session_output_tokens)
        resp = await self.adapter.complete(
            model=self.cfg.model,
            messages=[
                {'role': 'system', 'content': 'Synthesize the task results into a clear, complete answer.'},
                {'role': 'user', 'content': f"Original request: {user_message}\n\nResults:\n{summary}"}
            ]
        )
        self.session_input_tokens += resp.input_tokens
        self.session_output_tokens += resp.output_tokens
        answer = resp.content.strip()
        await self.db.add_message(self.user_id, 'user', user_message)
        await self.db.add_message(self.user_id, 'assistant', answer)
        print(f'{Fore.GREEN}Assistant>{Style.RESET_ALL} {answer}')
        turn_in = self.session_input_tokens - tokens_before[0]
        turn_out = self.session_output_tokens - tokens_before[1]
        if turn_in or turn_out:
            self._print_token_summary(turn_in, turn_out)
        return answer
