import asyncio
import json
from typing import List, Dict, Optional

from rich.markdown import Markdown
from rich.text import Text

from common.config import config
from tools.manager import simple_tools, executor_tools, tool_handler
from tools.todo import ToDoManager, PlanItemStatus
from memory.db import DB
from agent.base import Agent
from agent.profile import ProfileManager
from cli.theme import console


def _strip_orphaned_tool_messages(messages: List[Dict]) -> List[Dict]:
    valid_ids = {
        tc['id']
        for m in messages
        if m.get('role') == 'assistant'
        for tc in (m.get('tool_calls') or [])
    }
    return [m for m in messages if m.get('role') != 'tool' or m.get('tool_call_id') in valid_ids]


class MainAgent(Agent):
    def __init__(self, cfg: config, tools: Optional[List] = None,
                 db: DB = None, user_id: str = 'default_user'):
        super().__init__(cfg, tools if tools is not None else simple_tools)
        self.db = db
        self.user_id = user_id
        self.todo_manager = ToDoManager()
        self._profile = ProfileManager(db, user_id, cfg, self.adapter)
        self._last_user_message = ''
        self.mode = 'simple'

    def _task_complete(self) -> bool:
        if not self.todo_manager.items:
            return True
        return all(i.status == PlanItemStatus.COMPLETED for i in self.todo_manager.items)

    async def _call_tool(self, name: str, args: dict) -> str:
        if name == 'to_do':
            return self.todo_manager.to_do(**args)
        return await tool_handler[name](**args)

    async def _save_turn(self, msg: Dict):
        role = msg.get('role')
        content = msg.get('content')
        tool_call_id = msg.get('tool_call_id')
        await self.db.add_message(self.user_id, role, content, tool_call_id)

        if role == 'user':
            self._last_user_message = content
        elif role == 'assistant' and self._last_user_message:
            asyncio.create_task(self._profile.update(self._last_user_message, content))

    async def _build_system_prompt(self) -> str:
        profile = await self.db.get_user_profile(self.user_id)
        profile_text = json.dumps(profile, indent=2) if profile else "No profile yet."
        return self.cfg.system_prompt.format(user_profile=profile_text)

    async def _build_messages(self, user_message: str) -> List[Dict]:
        limit = self.cfg.context_window
        history, _ = await self.db.get_recent_history(self.user_id, limit=limit)
        messages = _strip_orphaned_tool_messages(list(history))

        await self._save_turn({'role': 'user', 'content': user_message})
        messages.append({'role': 'user', 'content': user_message})
        return messages

    def _print_token_summary(self, turn_input: int, turn_output: int):
        total = self.session_input_tokens + self.session_output_tokens
        t = Text(justify='right')
        t.append(f'↑ {turn_input:,} ↓ {turn_output:,}', style='dim')
        t.append('  ·  session ', style='dim')
        t.append(f'↑ {self.session_input_tokens:,} ↓ {self.session_output_tokens:,}', style='dim')
        t.append(f'  ({total:,} total)', style='dim cyan')
        console.print(t)

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

    async def _reason_about_plan(self, user_message: str, tasks: list[str]) -> str:
        with console.status('[dim cyan]Reasoning through plan…[/]', spinner='dots'):
            resp = await self.adapter.complete(
                model=self.cfg.model,
                messages=[
                    {'role': 'system', 'content': self.cfg.reasoning_prompt},
                    {'role': 'user', 'content': f'Request: {user_message}\n\nPlanned tasks:\n' +
                     '\n'.join(f'{i+1}. {t}' for i, t in enumerate(tasks))},
                ]
            )
        self.session_input_tokens += resp.input_tokens
        self.session_output_tokens += resp.output_tokens
        reasoning = resp.content.strip()
        console.print(Text(reasoning, style='dim'))
        return reasoning

    async def _run_deep(self, user_message: str) -> str:
        from agent.planner import PlannerAgent
        from agent.evaluator import EvaluatorAgent

        with console.status('[agent.deep]Planning…[/]', spinner='dots'):
            tasks = await PlannerAgent(self.cfg).run(user_message)

        console.print(f'[agent.deep]▸ Plan[/]  [dim]{len(tasks)} task(s)[/]')
        for i, t in enumerate(tasks):
            console.print(f'  [dim]{i+1}.[/] {t}')

        reasoning = await self._reason_about_plan(user_message, tasks)
        context = f'{user_message}\n\n[Reasoning]\n{reasoning}'

        with console.status('[agent.deep]Starting executors…[/]', spinner='dots'):
            results = await self._run_executors(tasks, context)

        for round_num in range(3):
            with console.status(f'[agent.deep]Evaluating (round {round_num + 1})…[/]', spinner='dots'):
                evaluation = await EvaluatorAgent(self.cfg).evaluate(user_message, results)
            if evaluation.passed:
                console.print('[agent.success]✓ Evaluation passed.[/]')
                break
            if not evaluation.issues:
                break
            console.print(f'[agent.warn]⚠ {len(evaluation.issues)} issue(s) — spawning fix executors…[/]')
            results.extend(await self._run_executors(evaluation.issues, context))

        return await self._synthesize(user_message, results)

    async def _run_executors(self, tasks: list[str], context: str) -> list[dict]:
        from agent.executor import ExecutorAgent

        async def run_one(task: str, idx: int) -> dict:
            console.print(f'  [agent.executor]▸ Executor {idx+1}[/]  [dim]{task}[/]')
            try:
                result = await ExecutorAgent(self.cfg, tools=executor_tools).run(task, context)
            except Exception as e:
                result = f"Executor error: {e}"
            console.print(f'  [agent.executor]✓ Executor {idx+1}[/] [dim]done[/]')
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
        if not self._silent:
            console.print()
            console.print(Markdown(answer))
        turn_in = self.session_input_tokens - tokens_before[0]
        turn_out = self.session_output_tokens - tokens_before[1]
        if turn_in or turn_out:
            self._print_token_summary(turn_in, turn_out)
        return answer
