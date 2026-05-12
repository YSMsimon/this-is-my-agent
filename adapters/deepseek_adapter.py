from typing import Callable
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

    def complete(self, messages: list[dict], model: str, tools: list[dict] | None = None,
                 stream: bool = False, on_chunk: Callable[[str], None] | None = None) -> Response:
        if stream:
            content = ''
            reasoning = ''
            finish_reason = ''
            tool_calls_raw: dict[int, dict] = {}

            for chunk in self.client.chat.completions.create(
                model=model, messages=messages, tools=tools or None, stream=True
            ):
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason or finish_reason

                if getattr(delta, 'reasoning_content', None):
                    reasoning += delta.reasoning_content
                if delta.content:
                    content += delta.content
                    if on_chunk:
                        on_chunk(delta.content)
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

            self._response = Response(
                content=content,
                reasoning=reasoning,
                tool_calls=[
                    {'id': tc['id'], 'type': 'function',
                     'function': {'name': tc['name'], 'arguments': tc['arguments']}}
                    for tc in (tool_calls_raw[i] for i in sorted(tool_calls_raw))
                ],
                model=model,
                finish_reason=finish_reason,
            )
        else:
            raw = self.client.chat.completions.create(
                model=model, messages=messages, tools=tools or None,
            )
            msg = raw.choices[0].message
            self._response = Response(
                content=msg.content or '',
                reasoning=getattr(msg, 'reasoning_content', '') or '',
                tool_calls=[
                    {'id': tc.id, 'type': 'function',
                     'function': {'name': tc.function.name, 'arguments': tc.function.arguments}}
                    for tc in (msg.tool_calls or [])
                ],
                model=raw.model,
                finish_reason=raw.choices[0].finish_reason,
            )

        return self._response

    @property
    def response(self) -> Response:
        return self._response
