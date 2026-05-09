import re
from pydantic import BaseModel, ValidationError
from agent.base import Agent
from common.config import config


def _strip_fence(text: str) -> str:
    return re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())


class EvalOutput(BaseModel):
    passed: bool
    issues: list[str]


class EvaluatorAgent(Agent):
    def __init__(self, cfg: config):
        super().__init__(cfg, tools=[])

    async def evaluate(self, user_message: str, results: list[dict]) -> EvalOutput:
        summary = "\n\n".join(
            f"Task {i+1}: {r['task']}\nResult: {r['result']}"
            for i, r in enumerate(results)
        )
        messages = [
            {'role': 'system', 'content': self.cfg.evaluator_prompt},
            {'role': 'user', 'content': f"Original request: {user_message}\n\nCompleted tasks:\n{summary}"}
        ]
        for attempt in range(2):
            resp = await self.client.chat(
                model=self.cfg.evaluator_model,
                messages=messages,
                format=EvalOutput.model_json_schema(),
                options={'temperature': 0}
            )
            try:
                return EvalOutput.model_validate_json(_strip_fence(resp.message.content))
            except (ValidationError, ValueError):
                messages.append({'role': 'assistant', 'content': resp.message.content})
                messages.append({'role': 'user', 'content':
                    f'Return your answer as a JSON object matching this schema: {EvalOutput.model_json_schema()}'
                })
        raise ValueError(f"Evaluator failed to return valid JSON: {resp.message.content}")

    async def run(self, user_message: str) -> str:
        raise NotImplementedError("Use evaluate() directly")
