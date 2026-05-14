import asyncio
from adapters.ollama_adapter import OllamaAdapter
from common.config import config


async def main():
    adapter = OllamaAdapter(config())
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the weather in New York City?"},
    ]
    messages = messages * 100000
    response = await adapter.complete(
        messages,
        model="qwen3-coder-next:cloud",
        stream=True,
        on_chunk=lambda chunk: print(chunk, end='', flush=True),
    )
    print(response.content)



asyncio.run(main())
