import re
from pydantic import BaseModel, ValidationError
from agent.base import Agent
from common.config import config


def _strip_fence(text: str) -> str:
    return re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())


class PlanOutput(BaseModel):
    tasks: list[str]


class PlannerAgent(Agent):
    def __init__(self, cfg: config):
        super().__init__(cfg, tools=[])

    async def run(self, user_message: str) -> list[str]:
        messages = [
            {'role': 'system', 'content': self.cfg.planner_prompt + '\nRespond with JSON.'},
            {'role': 'user', 'content': user_message}
        ]
        for attempt in range(2):
            resp = await self.adapter.complete(
                model=self.cfg.planner_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = resp.content
            try:
                return PlanOutput.model_validate_json(_strip_fence(content)).tasks
            except (ValidationError, ValueError):
                messages.append({'role': 'assistant', 'content': content})
                messages.append({'role': 'user', 'content':
                    f'Return your answer as a JSON object matching this schema: {PlanOutput.model_json_schema()}'
                })
        raise ValueError(f"Planner failed to return valid JSON: {content}")
