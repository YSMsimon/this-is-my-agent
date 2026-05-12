from adapters.deepseek_adapter import DeepSeekAdapter
from common.config import config

weather_tool = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a given city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city name, e.g. New York City"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit"
                }
            },
            "required": ["city"]
        }
    }
}

adapter = DeepSeekAdapter(config())

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "tell me step to eat an apple"}
]

response = adapter.complete(
    messages,
    model="deepseek-chat",
    tools=[weather_tool],
    stream=True,
    on_chunk=lambda chunk: print(chunk, end='', flush=True)
)

print()
print("Finish reason:", response.finish_reason)
print("Tool calls:", response.tool_calls)
