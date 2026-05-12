from openai import OpenAI
from common.config import config
from adapters.schema import Response


class DeepSeekAdapter:
    def __init__(self, cfg: config):
        self.client = OpenAI(
            api_key=cfg.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        self._response: Response | None = None

    def generate_response(self, messages: list[dict], model: str, tools: list[dict] | None = None):
        content = ''
        reasoning = ''
        finish_reason = ''
        tool_calls_raw: dict[int, dict] = {}

        stream = self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            tools=tools or None,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason or finish_reason

            if getattr(delta, 'reasoning_content', None):
                reasoning += delta.reasoning_content

            if delta.content:
                content += delta.content
                yield delta.content

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_raw:
                        tool_calls_raw[idx] = {'id': '', 'name': '', 'arguments': ''}
                    if tc.id:
                        tool_calls_raw[idx]['id'] = tc.id
                    if tc.function.name:
                        tool_calls_raw[idx]['name'] += tc.function.name
                    if tc.function.arguments:
                        tool_calls_raw[idx]['arguments'] += tc.function.arguments

        tool_calls = [
            {'id': tc['id'], 'type': 'function',
             'function': {'name': tc['name'], 'arguments': tc['arguments']}}
            for tc in (tool_calls_raw[i] for i in sorted(tool_calls_raw))
        ]

        self._response = Response(
            content=content,
            reasoning=reasoning,
            tool_calls=tool_calls,
            model=model,
            finish_reason=finish_reason,
        )

    def complete(self, messages: list[dict], model: str, tools: list[dict] | None = None) -> Response:
        for _ in self.generate_response(messages, model, tools):
            pass
        return self._response

    @property
    def response(self) -> Response:
        return self._response
