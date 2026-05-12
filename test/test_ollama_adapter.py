from adapters.ollama_adapter import OllamaAdapter
from common.config import config
from test.test_tools import tools
adapter = OllamaAdapter(config())
"""
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the weather in New York City?"}
]

response = adapter.complete(
    messages,
    model="qwen3-coder-next:cloud",
    stream=False,
    tools = tools,
    on_chunk=lambda chunk: print(chunk, end='', flush=True)
)

print()
print("Finish reason:", response.finish_reason)
print("Tool calls:", response.tool_calls)
"""

message = "What is the weather in New York City?"

response = adapter.embed(message, model="nomic-embed-text")
print("Embedding:", response)