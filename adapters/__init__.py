from typing import Callable
from adapters.ollama_adapter import OllamaAdapter
from adapters.deepseek_adapter import DeepSeekAdapter
from adapters.schema import Response
from common.config import config


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
                    self._providers[provider] = OllamaAdapter(self._cfg)
                case 'deepseek':
                    self._providers[provider] = DeepSeekAdapter(self._cfg)
                case _:
                    raise ValueError(f"Unsupported provider: {provider}")
        return self._providers[provider], model_name

    def complete(self, messages: list[dict], model: str, tools: list[dict] | None = None,
                 stream: bool = False, on_chunk: Callable[[str], None] | None = None, **kwargs) -> Response:
        provider, model_name = self._get(model)
        return provider.complete(messages, model_name, tools, stream, on_chunk, **kwargs)

    def embed(self, text: str, model: str) -> list[float]:
        provider, model_name = self._get(model)
        return provider.embed(text, model_name)
