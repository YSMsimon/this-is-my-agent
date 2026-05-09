from typing import List, Optional
from agent.base import Agent
from common.config import config


class ExecutorAgent(Agent):
    def __init__(self, cfg: config, tools: Optional[List] = None):
        super().__init__(cfg, tools)

    async def run(self, task: str, context: str = '') -> str:
        self._system_prompt = self.cfg.executor_prompt
        content = f"Context: {context}\n\nYour task: {task}" if context else task
        messages = [{'role': 'user', 'content': content}]
        final_messages = await self._execute(messages)
        return next(
            (m.get('content', '') for m in reversed(final_messages)
             if isinstance(m, dict) and m.get('role') == 'assistant'),
            ''
        )
