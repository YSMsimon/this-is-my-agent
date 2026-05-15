import os
from adapters.openai_compat_adapter import OpenAICompatAdapter
from adapters.ollama_adapter import OllamaAdapter
from adapters.schema import Response
from common.config import config

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class Adapter:
    def __init__(self, cfg: config):
        self._cfg = cfg
        self._providers: dict = {}

    def _get(self, model: str):
        if '/' not in model:
            raise ValueError(f"Model must be in 'provider/model' format, got: {model}")
        provider, model_name = model.split('/', 1)
        if provider not in self._providers:
            match provider:
                case 'ollama':
                    self._providers[provider] = OllamaAdapter(
                        api_key=os.getenv('OLLAMA_API_KEY', 'dummy'),
                        base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1'),
                    )
                case 'deepseek':
                    self._providers[provider] = OpenAICompatAdapter(
                        api_key=os.getenv('DEEPSEEK_API_KEY', ''),
                        base_url=_DEEPSEEK_BASE_URL,
                        provider='deepseek',
                    )
                case 'openai':
                    self._providers[provider] = OpenAICompatAdapter(
                        api_key=os.getenv('OPENAI_API_KEY', ''),
                        provider='openai',
                    )
                case 'external':
                    self._providers[provider] = OpenAICompatAdapter(
                        api_key=os.getenv('EXTERNAL_API_KEY', ''),
                        base_url=os.getenv('EXTERNAL_BASE_URL', 'https://openrouter.ai/api/v1'),
                        provider='external',
                    )
                case _:
                    raise ValueError(f"Unsupported provider: {provider}")
        return self._providers[provider], model_name

    async def complete(self, messages: list[dict], model: str, tools: list[dict] | None = None,
                       stream: bool = False, on_chunk=None, **kwargs) -> Response:
        provider, model_name = self._get(model)
        return await provider.complete(messages, model_name, tools, stream, on_chunk, **kwargs)

