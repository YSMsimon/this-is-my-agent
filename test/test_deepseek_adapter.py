import asyncio
from adapters.deepseek_adapter import DeepSeekAdapter
from common.config import config


async def main():
    adapter = DeepSeekAdapter(config())

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me one step to eat an apple."},
    ]
    messages = messages * 1000000
    response = await adapter.complete(
        messages,
        model="deepseek-chat",
        stream=True,
        on_chunk=lambda chunk: print(chunk, end='', flush=True),
    )
    print(response.content)
    print("Finish reason:", response.finish_reason)
    print("Input tokens:", response.input_tokens)
    print("Output tokens:", response.output_tokens)



asyncio.run(main())
