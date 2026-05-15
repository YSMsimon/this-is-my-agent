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
                    self._providers[provider] = OllamaAdapter(self._cfg)
                case 'deepseek':
                    self._providers[provider] = OpenAICompatAdapter(
                        api_key=self._cfg.deepseek_api_key,
                        base_url=_DEEPSEEK_BASE_URL,
                        provider='deepseek',
                    )
                case 'openai':
                    self._providers[provider] = OpenAICompatAdapter(
                        api_key=self._cfg.openai_api_key,
                        provider='openai',
                    )
                case 'external':
                    self._providers[provider] = OpenAICompatAdapter(
                        api_key=self._cfg.external_api_key,
                        base_url=self._cfg.external_base_url,
                        provider='external',
                    )
                case _:
                    raise ValueError(f"Unsupported provider: {provider}")
        return self._providers[provider], model_name

    async def complete(self, messages: list[dict], model: str, tools: list[dict] | None = None,
                       stream: bool = False, on_chunk=None, **kwargs) -> Response:
        provider, model_name = self._get(model)
        return await provider.complete(messages, model_name, tools, stream, on_chunk, **kwargs)

    async def embed(self, text: str, model: str) -> list[float]:
        provider, model_name = self._get(model)
        return await provider.embed(text, model_name)
