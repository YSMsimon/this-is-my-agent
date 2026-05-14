from openai import AsyncOpenAI, RateLimitError, BadRequestError, NotFoundError, APIStatusError
from common.config import config
from adapters.schema import Response


def _is_context_exceeded(e: BadRequestError) -> bool:
    return 'maximum context length' in str(e).lower()


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
        except NotFoundError as e:
            raise RuntimeError(f"Model not found: {model}") from e
        except BadRequestError as e:
            if _is_context_exceeded(e):
                raise RuntimeError("context_window_exceeded") from e
            raise
        except APIStatusError as e:
            if e.status_code == 413:
                raise RuntimeError("context_window_exceeded") from e
            raise

    async def _complete(self, messages, model, tools=None, **kwargs) -> Response:
        raw = await self.client.chat.completions.create(
            model=model, messages=messages, tools=tools or None, **kwargs
        )
        msg = raw.choices[0].message
        usage = raw.usage
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
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    async def _stream(self, messages, model, tools=None, on_chunk=None, **kwargs) -> Response:
        content = ''
        reasoning = ''
        finish_reason = ''
        tool_calls_raw: dict[int, dict] = {}
        input_tokens = 0
        output_tokens = 0

        stream = await self.client.chat.completions.create(
            model=model, messages=messages, tools=tools or None, stream=True,
            stream_options={"include_usage": True}, **kwargs
        )
        async for chunk in stream:
            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens
                output_tokens = chunk.usage.completion_tokens
                continue
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
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
