from openai import AsyncOpenAI, RateLimitError
from common.config import config
from adapters.schema import Response


class DeepSeekAdapter:
    def __init__(self, cfg: config):
        self.client = AsyncOpenAI(
            api_key=cfg.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )

    async def complete(self, messages: list[dict], model: str, tools: list[dict] | None = None,
                       stream: bool = False, on_chunk=None, **kwargs) -> Response:
        try:
            if stream:
                return await self._stream(messages, model, tools, on_chunk, **kwargs)
            return await self._complete(messages, model, tools, **kwargs)
        except RateLimitError as e:
            raise RuntimeError(f"DeepSeek rate limit reached: {e}") from e

    async def _complete(self, messages, model, tools=None, **kwargs) -> Response:
        raw = await self.client.chat.completions.create(
            model=model, messages=messages, tools=tools or None, **kwargs
        )
        msg = raw.choices[0].message
        return Response(
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

    async def _stream(self, messages, model, tools=None, on_chunk=None, **kwargs) -> Response:
        content = ''
        reasoning = ''
        finish_reason = ''
        tool_calls_raw: dict[int, dict] = {}

        stream = await self.client.chat.completions.create(
            model=model, messages=messages, tools=tools or None, stream=True, **kwargs
        )
        async for chunk in stream:
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

        return Response(
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
