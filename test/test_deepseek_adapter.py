from adapters.deepseek_adapter import DeepSeekAdapter
from common.config import config
from test_tools import tools
adapter = DeepSeekAdapter(config())

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "tell me step to eat an apple"}
]

response = adapter.complete(
    messages,
    model="deepseek-chat",
    tools=tools,
    stream=True,
    on_chunk=lambda chunk: print(chunk, end='', flush=True)
)

print()
print("Finish reason:", response.finish_reason)
print("Tool calls:", response.tool_calls)
